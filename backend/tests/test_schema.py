"""Database schema tests (run against the separate *_test database; see conftest.py).

They check that:
- the migrations create exactly the tables in app/models, and can be rolled back and re-applied;
- SQLAlchemy can create and read linked records through the relationships;
- pgvector stores embeddings and answers "most similar skill" queries;
- the important constraints reject bad data.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    EMBEDDING_DIM,
    AppUser,
    AuditLog,
    Base,
    Candidate,
    CandidateSkill,
    Course,
    CourseHealth,
    CourseModule,
    CourseOffering,
    DemandScore,
    District,
    DistrictPlan,
    Employer,
    EmployerRating,
    EmployerSurveyResponse,
    Enrollment,
    Equipment,
    Institute,
    InstituteEquipment,
    JobPosting,
    JobRole,
    ModuleSkill,
    Nos,
    NosSkill,
    PipelineRun,
    PlacementOutcome,
    Pledge,
    PostingSkill,
    QualificationPack,
    Recommendation,
    RoleEdge,
    RoleSkill,
    ScoringConfigVersion,
    Sector,
    SectorEvent,
    Skill,
    SkillAlias,
    SkillEquipment,
    Trainer,
    TrainerSkill,
    ValidationVote,
)
from app.models.enums import CourseType, EducationLevel, EmployerSize, InstituteType, SkillType
from tests.conftest import alembic_config

pytestmark = pytest.mark.db

# Every test record is labelled synthetic, like all demo data.
SYN = {"source": "TEST", "is_synthetic": True}
NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
# Looks like an argon2id hash (the database only accepts those); not a real password.
FAKE_ARGON2_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdA"


def vec(*head: float) -> list[float]:
    """A 384-number embedding: the given numbers followed by zeros."""
    return list(head) + [0.0] * (EMBEDDING_DIM - len(head))


def evidence(n: int) -> list[dict]:
    return [
        {"type": "POSTING_TREND", "summary": f"evidence item {i + 1}", "is_synthetic": True}
        for i in range(n)
    ]


@pytest.fixture
def g(db_session: Session) -> SimpleNamespace:
    """A small connected graph: district, sector, roles, skills, course, institute, employer."""
    s = db_session
    district = District(
        code="MH-NASHIK",
        name="Nashik",
        state_name="Maharashtra",
        aliases=["Nasik", "Ambad MIDC"],
        official_code="TODO-VERIFY",  # allowed while not verified
        official_code_scheme="LGD",
        **SYN,
    )
    sector = Sector(code="EV", name="Electric Vehicles", **SYN)
    role = JobRole(
        code="ev-charging-technician",
        title="EV Charging Technician",
        sector=sector,
        nsqf_level=Decimal("4.0"),
        **SYN,
    )
    senior = JobRole(
        code="senior-ev-technician", title="Senior EV Technician", sector=sector, **SYN
    )

    charger = Skill(
        code="install-ev-charger",
        name="Install EV charging equipment",
        skill_type=SkillType.TECHNICAL,  # enum member; stored as its text value
        embedding=vec(1.0),
        embedding_model="test-model",
        **SYN,
    )
    hv = Skill(
        code="hv-safety",
        name="Apply high-voltage safety procedures",
        skill_type=SkillType.SAFETY,
        embedding=vec(0.9, 0.1),
        embedding_model="test-model",
        **SYN,
    )
    wiring = Skill(
        code="domestic-wiring",
        name="Carry out domestic wiring",
        skill_type=SkillType.TECHNICAL,
        embedding=vec(0.0, 1.0),
        embedding_model="test-model",
        **SYN,
    )
    charger.aliases += [
        SkillAlias(
            alias="EV charger installation", alias_normalized="ev charger installation", **SYN
        ),
        SkillAlias(
            alias="ईवी चार्जर लगाना", alias_normalized="ईवी चार्जर लगाना", language="hi", **SYN
        ),
    ]
    role.skill_links += [
        RoleSkill(skill=charger, importance=1.0, required_band=2, **SYN),
        RoleSkill(skill=hv, importance=0.8, required_band=2, **SYN),
    ]
    role.outgoing_edges.append(RoleEdge(to_role=senior, typical_training_hours=120, **SYN))

    qp = QualificationPack(
        code="qp-ev-service-test",
        title="EV Service Technician (test)",
        sector=sector,
        job_role=role,
        official_code="TODO-VERIFY",
        official_code_scheme="NQR",
        **SYN,
    )
    nos = Nos(code="nos-ev-charging-test", title="Install charging equipment (test)", **SYN)
    qp.nos_units.append(nos)
    nos.skill_links.append(NosSkill(skill=charger, **SYN))

    course = Course(
        code="electrician-test",
        name="Electrician",
        course_type=CourseType.ITI_TRADE,
        sector=sector,
        qualification_pack=qp,
        duration_hours=2400,
        **SYN,
    )
    safety_module = CourseModule(sequence=1, title="Safety basics", hours=Decimal("20"), **SYN)
    wiring_module = CourseModule(sequence=2, title="Domestic wiring", hours=Decimal("40"), **SYN)
    course.modules += [wiring_module, safety_module]  # added out of order on purpose
    safety_module.skill_links.append(ModuleSkill(skill=hv, band_taught=1, **SYN))
    wiring_module.skill_links.append(ModuleSkill(skill=wiring, band_taught=2, **SYN))

    institute = Institute(
        code="example-iti-a",
        name="Example ITI A",
        institute_type=InstituteType.ITI,
        district=district,
        **SYN,
    )
    offering = CourseOffering(
        institute=institute,
        course=course,
        academic_year="2025-26",
        seats=80,
        seats_filled=72,
        completion_rate=0.8,
        **SYN,
    )
    trainer = Trainer(institute=institute, pseudonym="T-01", **SYN)
    trainer.skill_links.append(TrainerSkill(skill=hv, band=3, **SYN))
    kit = Equipment(
        code="ev-charger-kit",
        name="EV charger training unit",
        indicative_cost_inr=Decimal("150000"),
        **SYN,
    )
    kit.skill_links.append(SkillEquipment(skill=charger, qty_per_batch=2, **SYN))
    institute.equipment_items.append(InstituteEquipment(equipment=kit, quantity=0, **SYN))

    employer = Employer(
        code="example-ev-services",
        name="Example EV Services",
        district=district,
        sector=sector,
        size=EmployerSize.SMALL,
        **SYN,
    )
    config = ScoringConfigVersion(
        version="v1",
        config_sha256="a" * 64,
        config_yaml="weights: {}",
        is_active=True,
        approved_at=NOW,
    )
    run = PipelineRun(
        quarter="2026Q3",
        status="SUCCEEDED",
        is_current=True,
        config_version=config,
        started_at=NOW,
        finished_at=NOW,
    )

    s.add_all([district, role, senior, wiring, course, institute, employer, run])
    s.flush()
    return SimpleNamespace(**locals())


# ---------------------------------------------------------------- migrations
def test_database_has_exactly_the_model_tables(test_engine):
    tables = set(inspect(test_engine).get_table_names()) - {"alembic_version"}
    assert tables == set(Base.metadata.tables)
    assert len(tables) == 52  # 51 from the schema design + course_role (0004)


def test_skill_embedding_is_a_384_dimension_pgvector_column(test_engine):
    with test_engine.connect() as connection:
        column_type = connection.execute(
            text(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "WHERE attrelid = 'skill'::regclass AND attname = 'embedding'"
            )
        ).scalar_one()
    assert column_type == f"vector({EMBEDDING_DIM})"


def test_models_match_migrations(test_db_url):
    # Fails if someone changes a model but forgets to create a migration.
    command.check(alembic_config(test_db_url))


def test_migrations_roll_back_and_reapply(test_db_url, test_engine):
    config = alembic_config(test_db_url)
    test_engine.dispose()  # close pooled connections before dropping everything

    def table_count() -> int:
        with test_engine.connect() as connection:
            return connection.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name <> 'alembic_version'"
                )
            ).scalar_one()

    command.downgrade(config, "base")
    assert table_count() == 0
    command.upgrade(config, "head")
    assert table_count() == 52
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    assert table_count() == 52


# ---------------------------------------------------------------- create & read
def test_create_and_read_skill_graph(db_session, g):
    db_session.expire_all()  # force fresh reads from the database

    role = db_session.scalars(select(JobRole).where(JobRole.code == "ev-charging-technician")).one()
    assert role.sector.name == "Electric Vehicles"
    assert {link.skill.code for link in role.skill_links} == {"install-ev-charger", "hv-safety"}
    assert [edge.to_role.code for edge in role.outgoing_edges] == ["senior-ev-technician"]

    charger = db_session.scalars(select(Skill).where(Skill.code == "install-ev-charger")).one()
    assert {a.language for a in charger.aliases} == {"en", "hi"}
    assert len(list(charger.embedding)) == EMBEDDING_DIM
    assert list(charger.embedding)[:2] == [1.0, 0.0]

    qp = db_session.scalars(select(QualificationPack)).one()
    assert qp.nos_units[0].skill_links[0].skill.code == "install-ev-charger"

    course = db_session.scalars(select(Course)).one()
    assert [m.sequence for m in course.modules] == [1, 2]  # ordered by sequence
    assert course.modules[0].skill_links[0].skill.code == "hv-safety"

    institute = db_session.scalars(select(Institute)).one()
    assert institute.district.name == "Nashik"
    assert institute.offerings[0].course.name == "Electrician"
    assert institute.trainers[0].skill_links[0].band == 3
    assert institute.equipment_items[0].equipment.skill_links[0].skill.code == "install-ev-charger"


def test_enum_members_are_stored_as_plain_text(db_session, g):
    stored = db_session.execute(
        text("SELECT skill_type FROM skill WHERE code = 'install-ev-charger'")
    ).scalar_one()
    assert stored == "TECHNICAL"


def test_defaults_are_applied(db_session, g):
    db_session.expire_all()
    district = db_session.scalars(select(District)).one()
    assert district.id is not None
    assert district.created_at is not None and district.updated_at is not None
    assert district.official_code_verified is False
    assert db_session.scalars(select(SkillAlias)).first().language == "en"


def test_pgvector_finds_the_most_similar_skills(db_session, g):
    query = vec(1.0, 0.05)
    nearest = db_session.scalars(
        select(Skill).order_by(Skill.embedding.cosine_distance(query)).limit(2)
    ).all()
    assert [skill.code for skill in nearest] == ["install-ev-charger", "hv-safety"]


def test_demand_postings_and_outcomes(db_session, g):
    posting = JobPosting(
        title="EV Charging Technician (Fresher)",
        description="ITI Electrician. EV charger installation, safety.",
        employer=g.employer,
        district=g.district,
        location_raw="Ambad MIDC, Nashik",
        posted_on=date(2026, 8, 12),
        quarter="2026Q3",
        salary_min=Decimal("15000"),
        salary_max=Decimal("18000"),
        salary_period="MONTH",
        dedupe_key="d" * 64,
        **SYN,
    )
    posting.skill_links.append(
        PostingSkill(skill=g.charger, confidence=1.0, method="ALIAS", band=2)
    )
    survey = EmployerSurveyResponse(
        employer=g.employer,
        district=g.district,
        channel="WEB",
        language="mr",
        consent_given=True,
        roles_json=[{"role_id": str(g.role.id), "count": 5, "timeframe_months": 12}],
        **SYN,
    )
    candidate = Candidate(
        pseudonym="C-000001",
        district=g.district,
        education_level=EducationLevel.CLASS_12,
        languages=["mr", "en"],
        **SYN,
    )
    candidate.skill_links.append(CandidateSkill(skill=g.wiring, band=1, **SYN))
    enrollment = Enrollment(
        candidate=candidate,
        course_offering=g.offering,
        status="COMPLETED",
        enrolled_on=date(2025, 8, 1),
        completed_on=date(2026, 7, 31),
        **SYN,
    )
    outcome = PlacementOutcome(
        enrollment=enrollment,
        placed=True,
        placement_type="WAGE",
        employer=g.employer,
        role=g.role,
        salary_monthly_inr=Decimal("16000"),
        placed_on=date(2026, 9, 1),
        **SYN,
    )
    outcome.rating = EmployerRating(employer=g.employer, rating=4, **SYN)
    db_session.add_all([posting, survey, candidate])
    db_session.flush()
    db_session.expire_all()

    saved = db_session.scalars(select(JobPosting)).one()
    assert saved.district.code == "MH-NASHIK"
    assert saved.skill_links[0].skill.code == "install-ev-charger"
    assert saved.extraction_status == "PENDING"  # default
    assert db_session.scalars(select(EmployerSurveyResponse)).one().roles_json[0]["count"] == 5

    saved_candidate = db_session.scalars(select(Candidate)).one()
    placement = saved_candidate.enrollments[0].placement_outcome
    assert placement.placed and placement.employer.name == "Example EV Services"
    assert placement.rating.rating == 4


def test_intelligence_recommendation_votes_pledges_and_plan(db_session, g):
    health = CourseHealth(
        pipeline_run=g.run,
        course_offering=g.offering,
        score=58.0,
        coverage=0.35,
        flags=["OUTDATED"],
        confidence="MEDIUM",
        synthetic_share=1.0,
        components_json=[{"name": "coverage", "weight": 0.3, "value": 0.35}],
        evidence_json=evidence(2),
    )
    demand = DemandScore(
        pipeline_run=g.run,
        district=g.district,
        quarter="2026Q3",
        skill=g.charger,
        score=81.5,
        mention_count=110,
        trend_status="EMERGING",
        confidence="MEDIUM",
        synthetic_share=1.0,
    )
    rec = Recommendation(
        fingerprint="f" * 64,
        rec_type="ADD_MODULE",
        priority="HIGH",
        confidence="MEDIUM",
        decision_owner="DGT_PROCESS",
        district=g.district,
        institute=g.institute,
        course_offering=g.offering,
        skill=g.charger,
        payload_json={"module_title": "EV charging installation and HV safety"},
        evidence_json=evidence(3),
        synthetic_share=1.0,
        first_run=g.run,
        last_seen_run=g.run,
    )
    rec.votes.append(ValidationVote(employer=g.employer, vote="APPROVE", is_synthetic=True))
    rec.pledges.append(
        Pledge(employer=g.employer, pledge_type="APPRENTICE", count=10, timeframe_months=12)
    )
    plan = DistrictPlan(
        district=g.district,
        quarter="2026Q3",
        status="GENERATED",
        pipeline_run=g.run,
        content_json={"note": "frozen copy of the plan"},
        generated_at=NOW,
        synthetic_share=1.0,
    )
    user = AppUser(
        email="officer.nashik@example.test",
        password_hash=FAKE_ARGON2_HASH,
        display_name="Demo District Officer",
        role="district_officer",
        district=g.district,
        is_demo=True,
    )
    db_session.add_all([health, demand, rec, plan, user])
    db_session.flush()
    db_session.add(AuditLog(user=user, action="recommendation.vote", entity_type="recommendation"))
    db_session.flush()
    db_session.expire_all()

    saved = db_session.scalars(select(Recommendation)).one()
    assert saved.status == "DRAFT"  # default
    assert len(saved.evidence_json) == 3
    assert saved.votes[0].employer.code == "example-ev-services"
    assert sum(p.count for p in saved.pledges) == 10
    assert saved.first_run.is_current
    assert db_session.scalars(select(CourseHealth)).one().flags == ["OUTDATED"]
    assert db_session.scalars(select(DistrictPlan)).one().languages == ["en"]  # default


def test_deleting_a_skill_removes_its_aliases(db_session, g):
    db_session.delete(g.charger)
    db_session.flush()
    remaining = db_session.scalars(select(SkillAlias.alias_normalized)).all()
    assert remaining == []  # both aliases belonged to the deleted skill


# ---------------------------------------------------------------- constraints
# Rejected records are built with plain *_id values (not relationships), so they are never
# added to an existing object's list and cannot be re-flushed by accident later in a test.
def assert_rejected(session: Session, record: object, constraint: str) -> None:
    """The database must refuse `record`, naming `constraint` in the error."""
    with pytest.raises(IntegrityError) as error:
        with session.begin_nested():  # a savepoint: only this insert is undone
            session.add(record)
            session.flush()
    assert constraint in str(error.value)


def test_candidates_must_be_synthetic(db_session, g):
    real_person = Candidate(
        pseudonym="C-REAL",
        district_id=g.district.id,
        education_level="CLASS_12",
        source="TEST",
        is_synthetic=False,
    )
    assert_rejected(db_session, real_person, "ck_candidate_synthetic_only")


def test_survey_requires_consent(db_session, g):
    no_consent = EmployerSurveyResponse(
        district_id=g.district.id, channel="WEB", consent_given=False, **SYN
    )
    assert_rejected(db_session, no_consent, "ck_employer_survey_response_consent_required")


def test_recommendation_needs_two_evidence_items_or_limited_flag(db_session, g):
    weak = Recommendation(
        fingerprint="1" * 64,
        rec_type="ADD_MODULE",
        priority="HIGH",
        confidence="MEDIUM",
        district_id=g.district.id,
        evidence_json=evidence(1),
    )
    assert_rejected(db_session, weak, "ck_recommendation_evidence_required")

    limited_but_confident = Recommendation(
        fingerprint="2" * 64,
        rec_type="ADD_MODULE",
        priority="HIGH",
        confidence="MEDIUM",
        district_id=g.district.id,
        evidence_json=evidence(1),
        limited_evidence=True,
    )
    assert_rejected(
        db_session, limited_but_confident, "ck_recommendation_limited_evidence_low_confidence"
    )


def test_official_code_cannot_be_verified_while_todo(db_session, g):
    fake = District(
        code="MH-TEST",
        name="Test District",
        state_name="Maharashtra",
        official_code="TODO-VERIFY",
        official_code_verified=True,
        **SYN,
    )
    assert_rejected(db_session, fake, "ck_district_official_code_verified_requires_code")


def test_one_vote_per_employer_per_recommendation(db_session, g):
    rec = Recommendation(
        fingerprint="3" * 64,
        rec_type="EQUIPMENT",
        priority="LOW",
        confidence="LOW",
        district=g.district,
        evidence_json=evidence(2),
    )
    rec.votes.append(ValidationVote(employer=g.employer, vote="APPROVE"))
    db_session.add(rec)
    db_session.flush()
    duplicate = ValidationVote(recommendation_id=rec.id, employer_id=g.employer.id, vote="REJECT")
    assert_rejected(db_session, duplicate, "uq_validation_vote_recommendation_id_employer_id")


def test_only_one_current_pipeline_run(db_session, g):
    second = PipelineRun(
        quarter="2026Q4", status="SUCCEEDED", is_current=True, config_version_id=g.config.id
    )
    assert_rejected(db_session, second, "uq_pipeline_run_one_current")


def test_demand_score_is_for_a_role_or_a_skill_not_both(db_session, g):
    both = DemandScore(
        pipeline_run_id=g.run.id,
        district_id=g.district.id,
        quarter="2026Q3",
        role_id=g.role.id,
        skill_id=g.charger.id,
        score=50.0,
        confidence="LOW",
    )
    assert_rejected(db_session, both, "ck_demand_score_role_xor_skill")


def test_value_ranges_are_enforced(db_session, g):
    too_important = RoleSkill(
        role_id=g.senior.id, skill_id=g.wiring.id, importance=1.5, required_band=2, **SYN
    )
    assert_rejected(db_session, too_important, "ck_role_skill_importance_range")

    unknown_flag = CourseHealth(
        pipeline_run_id=g.run.id,
        course_offering_id=g.offering.id,
        score=50.0,
        coverage=0.5,
        flags=["MADE_UP_FLAG"],
        confidence="LOW",
    )
    assert_rejected(db_session, unknown_flag, "ck_course_health_flags_known")

    bad_quarter = SectorEvent(
        sector_id=g.sector.id,
        event_type="NEW_PLANT",
        title="Bad quarter",
        announced_on=date(2026, 9, 1),
        announced_quarter="2026-Q3",
        **SYN,
    )
    assert_rejected(db_session, bad_quarter, "ck_sector_event_announced_quarter_format")


def test_simulated_events_must_be_marked_synthetic(db_session, g):
    event = SectorEvent(
        sector_id=g.sector.id,
        district_id=g.district.id,
        event_type="NEW_PLANT",
        title="EV component plant (simulated)",
        expected_jobs=1200,
        announced_on=date(2026, 9, 1),
        announced_quarter="2026Q3",
        is_simulated=True,
        source="DEMO",
        is_synthetic=False,
    )
    assert_rejected(db_session, event, "ck_sector_event_simulated_is_synthetic")


def test_alias_text_is_unique_per_language(db_session, g):
    clash = SkillAlias(
        skill_id=g.hv.id,
        alias="EV Charger Installation",
        alias_normalized="ev charger installation",
        **SYN,
    )
    assert_rejected(db_session, clash, "uq_skill_alias_language")


def test_user_roles_need_their_scope(db_session, g):
    officer_without_district = AppUser(
        email="nobody@example.test",
        password_hash=FAKE_ARGON2_HASH,
        display_name="No scope",
        role="district_officer",
    )
    assert_rejected(db_session, officer_without_district, "ck_app_user_role_has_scope")
