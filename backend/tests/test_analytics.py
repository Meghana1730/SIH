"""Demand + supply + mismatch engine tests (app/analytics).

Formula tests use small hand-built inputs (no database). The planted-pattern, provenance
and API tests load the committed synthetic dataset into the test database.
"""

import math
import uuid
from datetime import date

import pytest

from app.analytics.demand import DemandEngine, percentile_ranks
from app.analytics.engine import compute, run_engine
from app.analytics.inputs import (
    Completion,
    Counts,
    EventInfo,
    Inputs,
    OfferingInfo,
    RoleInfo,
    SurveyAnswer,
    load_inputs,
)
from app.analytics.mismatch import classify, estimate_openings, mismatch_for
from app.analytics.queries import current_run, data_label
from app.analytics.supply import role_supply
from app.analytics.validation import validate
from app.config import load_config
from app.core.security import create_access_token
from app.core.settings import REPO_ROOT, Settings
from app.models import AppUser, District, Mismatch, PipelineRun
from app.models.enums import Confidence, MismatchStatus
from app.synthetic.export import read_export
from app.synthetic.loader import load_dataset

FAKE_ARGON2_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdA"
QUARTERS = ["2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2", "2026Q3"]


@pytest.fixture(scope="module")
def config():
    return load_config(settings=Settings(_env_file=None))


# ---------------------------------------------------------------- tiny hand-built world
D1, D2 = uuid.uuid4(), uuid.uuid4()
EV, WIRE = uuid.uuid4(), uuid.uuid4()


def world(**changes) -> Inputs:
    inputs = Inputs(
        quarters=QUARTERS,
        districts={D1: ("MH-NASHIK", "Nashik"), D2: ("MH-KOLHAPUR", "Kolhapur")},
        roles={
            EV: RoleInfo(EV, "ev-service-technician", "EV Service Technician", "EV"),
            WIRE: RoleInfo(WIRE, "wireman", "Wireman", "ELECTRICAL"),
        },
        skills={},
    )
    series = {
        (EV, D1): [2, 3, 4, 6, 8, 10],
        (WIRE, D1): [5, 5, 5, 5, 5, 5],
        (EV, D2): [1, 1, 1, 1, 1, 1],
        (WIRE, D2): [6, 5, 5, 4, 4, 3],
    }
    for (role, district), counts in series.items():
        for quarter, n in zip(QUARTERS, counts, strict=True):
            c = Counts()
            for _ in range(n):
                c.add(True)
            inputs.role_postings[(role, district, quarter)] = c
    inputs.posting_districts = {D1, D2}
    for key, value in changes.items():
        setattr(inputs, key, value)
    return inputs


def offering(district, role, filled, rate, year="2025-26", synthetic=True):
    return OfferingInfo(
        uuid.uuid4(),
        uuid.uuid4(),
        "EX-I",
        "Example ITI",
        uuid.uuid4(),
        "c",
        "Course",
        district,
        year,
        60,
        filled,
        rate,
        role,
        (),
        {},
        synthetic,
    )


# ---------------------------------------------------------------- 1. demand formula
def test_demand_is_the_weighted_sum_of_its_components(config):
    inputs = world(
        surveys=[
            SurveyAnswer(uuid.uuid4(), uuid.uuid4(), D1, "2026Q3", {EV: 10}, frozenset(), True)
        ],
        offerings=[offering(D1, EV, 40, 0.9, "2024-25")],
        completions=[Completion(uuid.uuid4(), date(2025, 7, 20), EV, True, True)],
    )
    inputs.completions = [Completion(inputs.offerings[0].id, date(2025, 7, 20), EV, True, True)]
    result = next(
        r
        for r in DemandEngine(inputs, config).roles("2026Q3")
        if (r.item_id, r.district_id) == (EV, D1)
    )
    weights = config.scoring.demand.weights.model_dump()
    available = [c for c in result.components if c.available]
    assert {c.name for c in available} == {"postings", "employer_survey", "absorption"}
    expected = sum(c.effective_weight * c.value for c in available)
    assert result.score == pytest.approx(round(expected, 2))
    total = sum(weights[c.name] for c in available)
    assert all(c.effective_weight == pytest.approx(weights[c.name] / total) for c in available)


# ---------------------------------------------------------------- 2. missing components
def test_missing_components_are_renormalised_not_zero(config):
    inputs = world()
    result = next(
        r
        for r in DemandEngine(inputs, config).roles("2026Q3")
        if (r.item_id, r.district_id) == (EV, D1)
    )
    postings = result.component("postings")
    assert [c.name for c in result.components if c.available] == ["postings"]
    assert postings.effective_weight == pytest.approx(1.0)  # 0.35 scaled up, not 0.35 x P
    assert result.score == pytest.approx(round(postings.value, 2))
    survey = result.component("employer_survey")
    assert not survey.available and survey.value is None and "no employer survey" in survey.note


# ---------------------------------------------------------------- 3. confidence
def test_confidence_follows_the_configured_rules(config):
    from app.analytics.demand import confidence_of

    assert confidence_of(3, 30, config) == Confidence.HIGH
    assert confidence_of(3, 29, config) == Confidence.MEDIUM  # "all" not met; 2 types -> medium
    assert confidence_of(1, 10, config) == Confidence.MEDIUM  # enough records
    assert confidence_of(1, 9, config) == Confidence.LOW
    few = world()
    result = next(
        r
        for r in DemandEngine(few, config).roles("2026Q3")
        if (r.item_id, r.district_id) == (EV, D2)
    )
    assert result.confidence == Confidence.LOW  # one source type, 4 postings


# ---------------------------------------------------------------- 4. posting growth
def test_posting_growth_is_clipped_and_ranked(config):
    inputs = world()
    inputs.role_postings[(EV, D2, "2026Q2")] = Counts(50, 50)  # 1+1 -> 50+1: growth clipped
    engine = DemandEngine(inputs, config)
    results = {(r.item_id, r.district_id): r for r in engine.roles("2026Q3")}
    clipped = results[(EV, D2)].component("postings").raw
    assert clipped["growth"] == config.scoring.demand.posting_signal.growth_max
    falling = results[(WIRE, D2)].component("postings").raw
    assert (falling["earlier_postings"], falling["recent_postings"]) == (9, 7) and falling[
        "growth"
    ] < 0
    ranks = percentile_ranks({"a": 1.0, "b": 2.0, "c": 2.0, "d": 3.0})
    assert ranks == {"a": 0.125, "b": 0.5, "c": 0.5, "d": 0.875}
    early = next(r for r in engine.roles("2025Q2") if (r.item_id, r.district_id) == (EV, D1))
    assert "history too short" in early.component("postings").note


# ---------------------------------------------------------------- 5. survey recency
def test_survey_answers_lose_weight_with_age(config):
    employer = uuid.uuid4()
    old = SurveyAnswer(uuid.uuid4(), employer, D1, "2026Q1", {EV: 8}, frozenset(), True)
    fresh = SurveyAnswer(uuid.uuid4(), uuid.uuid4(), D1, "2026Q3", {EV: 8}, frozenset(), True)
    result = next(
        r
        for r in DemandEngine(world(surveys=[old, fresh]), config).roles("2026Q3")
        if (r.item_id, r.district_id) == (EV, D1)
    )
    raw = result.component("employer_survey").raw
    half_life = config.scoring.demand.survey.half_life_quarters
    assert raw["decayed_headcount"] == pytest.approx(8 + 8 * 0.5 ** (2 / half_life))
    # Only the latest answer of an employer counts.
    newer = SurveyAnswer(uuid.uuid4(), employer, D1, "2026Q2", {EV: 1}, frozenset(), True)
    result = next(
        r
        for r in DemandEngine(world(surveys=[old, newer]), config).roles("2026Q3")
        if (r.item_id, r.district_id) == (EV, D1)
    )
    assert result.component("employer_survey").raw["headcount"] == 1


# ---------------------------------------------------------------- 6. absorption
def test_absorption_is_placements_in_the_role_per_completer(config):
    course = offering(D2, WIRE, 50, 0.9, "2024-25")
    completions = [
        Completion(course.id, date(2025, 7, 20), WIRE if i < 3 else None, i < 5, True)
        for i in range(10)
    ]
    engine = DemandEngine(world(offerings=[course], completions=completions), config)
    completers, placed, synthetic, years = engine.absorption_counts(WIRE, D2, "2026Q3")
    assert (completers, placed, synthetic, years) == (10, 3, 10, ["2024-25"])
    result = next(r for r in engine.roles("2026Q3") if (r.item_id, r.district_id) == (WIRE, D2))
    assert result.component("absorption").value == pytest.approx(30.0)
    # Cohorts not completed by the quarter do not count.
    assert engine.absorption_counts(WIRE, D2, "2025Q2")[0] == 0


# ---------------------------------------------------------------- 7. supply
def test_supply_is_seats_filled_times_completion_with_a_labelled_default(config):
    known, unknown = offering(D2, WIRE, 76, 0.9), offering(D2, WIRE, 50, None)
    supply = role_supply(world(offerings=[known, unknown]), config, WIRE, D2, "2025-26")
    default = config.scoring.supply.default_completion_rate
    assert supply.trained_output == pytest.approx(76 * 0.9 + 50 * default)
    assert supply.default_completion_used and supply.confidence == Confidence.MEDIUM
    assert any(a["name"] == "default completion rate" for a in supply.assumptions(config))
    none = role_supply(world(offerings=[known]), config, EV, D2, "2025-26")
    assert none.trained_output == 0 and none.data_available  # zero supply is data


# ---------------------------------------------------------------- 8. openings
def test_openings_use_the_role_coverage_factor(config):
    openings = estimate_openings(world(), config, WIRE, D2, "2026Q3")
    assert openings.postings == 5 + 4 + 4 + 3
    assert openings.value == pytest.approx(16 / 0.3) and openings.factor_label == "formal_heavy"
    settings = config.scoring.demand.openings.model_copy(
        update={"informal_heavy_roles": ["wireman"]}
    )
    demand = config.scoring.demand.model_copy(update={"openings": settings})
    informal = config.scoring.model_copy(update={"demand": demand})
    import dataclasses

    informal_config = dataclasses.replace(config, scoring=informal)
    assert estimate_openings(world(), informal_config, WIRE, D2, "2026Q3").value == pytest.approx(
        16 / 0.1
    )
    early = estimate_openings(world(), config, WIRE, D2, "2025Q3")
    assert early.annualised and early.value == pytest.approx((6 + 5) * 2 / 0.3)


# ---------------------------------------------------------------- 9-10. ratio and status
def test_mismatch_ratio_and_classification(config):
    inputs = world(offerings=[offering(D2, WIRE, 120, 0.9), offering(D1, WIRE, 10, 0.9)])
    result = mismatch_for(inputs, config, WIRE, D2, "2026Q3", None)
    assert result.ratio == pytest.approx(120 * 0.9 / (16 / 0.3), abs=1e-4)  # 2.03
    assert result.status == MismatchStatus.OVERSUPPLIED
    assert classify(0.69, config) == MismatchStatus.UNDERSUPPLIED
    assert classify(0.7, config) == classify(1.5, config) == MismatchStatus.BALANCED
    assert classify(1.51, config) == MismatchStatus.OVERSUPPLIED
    assert classify(None, config) == MismatchStatus.INSUFFICIENT_DATA
    assert MismatchStatus.UNDERSUPPLIED.value == "UNDER_SUPPLIED"
    no_courses = mismatch_for(world(), config, WIRE, D2, "2026Q3", None)
    assert no_courses.status == MismatchStatus.INSUFFICIENT_DATA  # no course data at all


def test_event_growth_signal_uses_the_lag_window(config):
    event = EventInfo(uuid.uuid4(), "Unit (synthetic)", "EV", D1, "2026Q2", 600, 0.6, True, True)
    engine = DemandEngine(world(events=[event]), config)
    jobs = engine.event_jobs(engine.inputs.roles[EV], D1, "2026Q2")
    assert jobs[0]["quarters"] == ["2026Q4", "2027Q1", "2027Q2"]  # +2..+5 within 4 quarters ahead
    assert jobs[0]["jobs_for_role"] == pytest.approx(600 * 0.6 / 4 * 3)  # only EV role here
    assert engine.event_jobs(engine.inputs.roles[EV], D1, "2026Q1") == []  # not announced yet


# ---------------------------------------------------------------- 11-14 on the synthetic dataset
@pytest.fixture
def loaded(db_session, config):
    dataset, _ = read_export(REPO_ROOT / config.synthetic.export_dir, config)
    load_dataset(db_session, dataset, config)
    return db_session


@pytest.mark.db
def test_engine_finds_the_planted_patterns(loaded, config):
    computation = compute(load_inputs(loaded, config), config)
    findings = validate(computation, config)
    assert [f.message for f in findings if not f.passed] == []
    ids = {f.id for f in findings}
    assert {"NASHIK-EV-SHORTAGE", "KOLHAPUR-OVERSUPPLY", "MOTOR-REWINDING-DECLINE"} <= ids


@pytest.mark.db
def test_stored_results_carry_provenance_and_synthetic_labels(loaded, config):
    summary = run_engine(loaded, config)
    run = current_run(loaded)
    assert run.id == summary.run_id and run.status == "SUCCEEDED"
    assert run.config_version.config_sha256 == config.scoring_sha256
    nashik = loaded.query(District).filter(District.code == "MH-NASHIK").one()
    rows = (
        loaded.query(Mismatch)
        .filter(
            Mismatch.pipeline_run_id == run.id,
            Mismatch.district_id == nashik.id,
            Mismatch.quarter == run.quarter,
        )
        .all()
    )
    ev = next(r for r in rows if r.role.code == "ev-service-technician")
    assert ev.status == "UNDER_SUPPLIED" and ev.synthetic_share == 1.0
    reasons = [e for e in ev.evidence_json if e["type"] == "reason"]
    assert {r["code"] for r in reasons} >= {
        "postings_increased",
        "industry_event",
        "training_supply_low",
    }
    assert all(r["is_synthetic"] for r in reasons)
    assumptions = {a["name"] for a in ev.evidence_json if a["type"] == "assumption"}
    assert "openings coverage factor" in assumptions
    assert data_label(ev.synthetic_share) == "demo data (synthetic)"
    # A second run becomes current; only one run is current.
    run_engine(loaded, config)
    assert loaded.query(PipelineRun).filter(PipelineRun.is_current.is_(True)).count() == 1


# ---------------------------------------------------------------- API
def _user(db, role, **scope):
    user = AppUser(
        email=f"{role}-{uuid.uuid4().hex[:6]}@example.org",
        password_hash=FAKE_ARGON2_HASH,
        display_name=role,
        role=role,
        **scope,
    )
    db.add(user)
    db.flush()
    token, _ = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.db
def test_api_explains_nashik_and_kolhapur_and_respects_scope(api, loaded, config):
    run_engine(loaded, config)
    admin = _user(loaded, "admin")
    item = api.get(
        "/api/v1/analytics/mismatch?district=MH-NASHIK&role=ev-service-technician", headers=admin
    ).json()["items"][0]
    assert item["status"] == "UNDER_SUPPLIED" and item["is_synthetic"] is True
    assert {"observed_inputs", "estimated_values", "assumptions", "confidence", "reasons"} <= set(
        item
    )
    kolhapur = api.get("/api/v1/analytics/districts/MH-KOLHAPUR/mismatch", headers=admin).json()
    wireman = next(r for r in kolhapur["roles"] if r["role"]["code"] == "wireman")
    assert wireman["status"] == "OVER_SUPPLIED" and kolhapur["mismatch_score"] > 0
    demand = api.get("/api/v1/analytics/demand/MH-NASHIK?sector=EV", headers=admin).json()
    assert {i["role"]["code"] for i in demand["items"]} == {
        "ev-service-technician",
        "ev-charging-installer",
    }
    skills = api.get(
        "/api/v1/analytics/demand?district=MH-NASHIK&skill=motor-rewinding", headers=admin
    ).json()
    assert skills["items"][0]["trend_status"] == "DECLINING"
    supply = api.get(
        "/api/v1/analytics/supply?district=MH-KOLHAPUR&group_by=institute", headers=admin
    ).json()
    assert supply["items"] and all(i["is_synthetic"] for i in supply["items"])
    nashik_id = loaded.query(District).filter(District.code == "MH-NASHIK").one().id
    officer = _user(loaded, "district_officer", district_id=nashik_id)
    assert (
        api.get("/api/v1/analytics/mismatch?district=MH-KOLHAPUR", headers=officer).status_code
        == 403
    )
    own = api.get("/api/v1/analytics/mismatch", headers=officer).json()
    assert {i["district"]["code"] for i in own["items"]} == {"MH-NASHIK"}
    candidate = _user(loaded, "candidate")
    assert api.get("/api/v1/analytics/demand", headers=candidate).status_code == 403


@pytest.mark.db
def test_api_without_a_run_says_how_to_get_one(api, db_session):
    admin = _user(db_session, "admin")
    response = api.get("/api/v1/analytics/demand", headers=admin)
    if db_session.query(PipelineRun).filter(PipelineRun.is_current.is_(True)).count() == 0:
        assert (
            response.status_code == 404 and "analytics run" in response.json()["detail"]["message"]
        )


def test_district_mismatch_uses_a_floor_for_zero_supply(config):
    floor = config.scoring.mismatch.district_ratio_floor
    assert abs(math.log(max(0.0, floor))) == pytest.approx(-math.log(floor))
