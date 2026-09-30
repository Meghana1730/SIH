"""Job intelligence pipeline tests: CSV ingestion -> skills -> role -> proficiency ->
evidence, batch processing, the API, and the pipeline against the synthetic dataset.

The vocabulary is the synthetic demo vocabulary (Y13) loaded from the committed export. A
fake word-overlap embedder stands in for the real model (fast, deterministic).
"""

import dataclasses
import uuid
from datetime import date

import pytest
from sqlalchemy import func, select

from app.cli.jobs import vocabulary_only
from app.config import load_config
from app.core.security import create_access_token
from app.core.settings import REPO_ROOT, Settings
from app.jobs.dedupe import posting_dedupe_key
from app.jobs.ingest import ingest_postings_csv, parse_date, scrub_contacts
from app.jobs.places import DistrictResolver
from app.jobs.processing import (
    GroundTruthConflict,
    JobIntelligence,
    posting_out,
    process_batch,
    process_posting,
)
from app.llm import LlmCallError, MockLLMClient
from app.models import AppUser, JobPosting, PostingRole, PostingSkill, ReviewItem
from app.models.enums import EvidenceKind, ExtractionMethod, Language, MatchDecision, Proficiency
from app.nlp.cues import first_years, load_cues
from app.nlp.skill_embeddings import embed_vocabulary
from app.nlp.tokens import analyze_text
from app.synthetic.export import read_export
from app.synthetic.ids import synthetic_id
from app.synthetic.loader import load_dataset
from tests.helpers import FakeEmbedder

pytestmark = pytest.mark.db

FAKE_ARGON2_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdA"
HEADER = (
    "title,description,employer,location,district,sector,posted_date,source,source_ref,"
    "license_note,is_synthetic"
)
NOTE = "SYNTHETIC test row"


@pytest.fixture(scope="module")
def config():
    return load_config(settings=Settings(_env_file=None))


@pytest.fixture(scope="module")
def export(config):
    dataset, _ = read_export(REPO_ROOT / config.synthetic.export_dir, config)
    return dataset


@pytest.fixture
def vocab(db_session, export, config):
    """The synthetic demo vocabulary (skills, aliases, roles, role skills) in the test DB."""
    load_dataset(db_session, vocabulary_only(export), config)
    return db_session


@pytest.fixture
def fake(vocab):
    # "scooter faults" means "EV diagnostics" to this fake model.
    embedder = FakeEmbedder({"scooter": "ev", "faults": "diagnostics"})
    embed_vocabulary(vocab, embedder)
    return embedder


@pytest.fixture
def intel(vocab, config, fake):
    return JobIntelligence(vocab, config, embedder=fake, llm=None)


def skills_of(analysis, kind=EvidenceKind.OBSERVED):
    return {h.skill.code: h for h in analysis.skills if h.evidence_kind == kind}


def csv_rows(*rows: str) -> bytes:
    return ("\n".join([HEADER, *rows]) + "\n").encode("utf-8")


def row(
    title,
    description="",
    *,
    district="Nashik",
    sector="EV",
    day="2026-09-10",
    source="Y16",
    synthetic="true",
    employer="Example EV Garage 90",
):
    description = f'"{description}"' if description else ""
    place = '"Ambad MIDC, Nashik"'
    return (
        f"{title},{description},{employer},{place},{district},{sector},{day},{source},"
        f'test row,"{NOTE}",{synthetic}'
    )


# ================================================================ skill extraction
def test_exact_skill_name_with_evidence(intel):
    analysis = intel.analyze("EV Service Technician", "Must know EV Diagnostics well.")
    hit = skills_of(analysis)["ev-diagnostics"]
    assert (hit.method, hit.decision, hit.confidence) == (
        ExtractionMethod.EXACT,
        MatchDecision.ACCEPT,
        1.0,
    )
    assert hit.field == "description" and hit.matched_text == "EV Diagnostics"
    text = "Must know EV Diagnostics well."
    assert text[hit.span[0] : hit.span[1]] == "EV Diagnostics"  # the span quotes the ad
    assert hit.evidence_text == "Must know EV Diagnostics well"


def test_alias_in_english_and_marathi(intel):
    english = skills_of(intel.analyze("EV Technician", "Battery diagnostics experience."))
    assert english["battery-management"].method == ExtractionMethod.ALIAS
    marathi = skills_of(intel.analyze("ईव्ही टेक्निशियन", "ईव्ही दोष निदान आवश्यक."))
    assert marathi["ev-diagnostics"].method == ExtractionMethod.ALIAS
    assert marathi["ev-diagnostics"].matched_text == "ईव्ही दोष निदान"


def test_fuzzy_match_catches_spelling_mistakes(intel, config):
    hit = skills_of(intel.analyze("Wireman", "Domestic wirring and cabel jointing."))[
        "electrical-wiring"
    ]
    assert hit.method == ExtractionMethod.FUZZY and hit.decision == MatchDecision.ACCEPT
    assert config.scoring.skill_matching.fuzzy.min_score <= hit.confidence < 1.0
    assert hit.matched_text == "Domestic wirring"


def test_embedding_match_finds_the_meaning(intel):
    hit = skills_of(intel.analyze("Mechanic", "Scooter faults."))["ev-diagnostics"]
    assert hit.method == ExtractionMethod.EMBEDDING and hit.matched_text == "Scooter faults"
    assert hit.similarity is not None


def test_unrelated_text_gives_no_skill_and_no_role(intel):
    analysis = intel.analyze("Accountant", "Tally and GST filing work in our office.")
    assert analysis.skills == [] and analysis.role is None and analysis.unknown == []


def test_unknown_skills_become_new_skill_candidates(intel):
    analysis = intel.analyze(
        "Maintenance Technician", "Skills required: PLC programming, SCADA and house wiring."
    )
    assert {u.text for u in analysis.unknown} == {"PLC programming", "SCADA"}
    assert set(skills_of(analysis)) == {"electrical-wiring"}  # the known skill is still found


def test_role_words_are_not_skill_phrases(intel):
    analysis = intel.analyze(
        "EV Technician",
        "EV technician required with battery diagnostics and charging station experience.",
    )
    observed = skills_of(analysis)
    assert set(observed) == {"battery-management", "ev-charging-systems"}
    inferred = skills_of(analysis, EvidenceKind.INFERRED)
    assert "ev-diagnostics" in inferred  # implied by the role, never presented as observed
    assert all(
        h.decision == MatchDecision.REVIEW and h.method == ExtractionMethod.ROLE_PROFILE
        for h in inferred.values()
    )


def test_requested_proficiency_is_detected_not_certified(intel):
    analysis = intel.analyze(
        "Electrician",
        "Expert in panel board wiring. Basic Motor Maintenance. 2-4 years experience.",
    )
    observed = skills_of(analysis)
    assert observed["panel-wiring"].proficiency == Proficiency.ADVANCED  # "Expert in"
    # "Basic" is part of the skill's own name, so it is not read as a level; the ad's
    # 2-4 years of experience decide instead.
    assert observed["motor-maintenance"].proficiency == Proficiency.INTERMEDIATE
    assert observed["motor-maintenance"].proficiency_cue.source == "posting years"
    assert (
        observed["panel-wiring"]
        .evidence_json()["proficiency_note"]
        .startswith("requested in the ad")
    )


# ================================================================ role matching
def test_role_from_title_alias_misspelling_and_description(intel):
    assert (
        intel.analyze("Electric Vehicle Mechanic", None).role.role.code == "ev-service-technician"
    )
    fuzzy = intel.analyze("EV Techncian", None).role
    assert fuzzy.role.code == "ev-service-technician" and fuzzy.method == ExtractionMethod.FUZZY
    described = intel.analyze("Job opening", "EV technician required for battery diagnostics.").role
    assert described.role.code == "ev-service-technician"
    assert "description mentions" in described.evidence_text


def test_role_from_skills_alone_is_only_a_review(intel, config):
    role = intel.analyze("Job opening", "Armature winding and coil winding of pump motors.").role
    assert role.role.code == "motor-rewinder" and role.method == ExtractionMethod.SKILL_PROFILE
    assert role.decision == MatchDecision.REVIEW
    assert role.confidence <= config.scoring.role_matching.skills_only_factor


def test_ambiguous_titles_go_to_review(intel):
    role = intel.analyze("Electrician / Wireman", "Wiring work in new buildings.").role
    assert role.decision == MatchDecision.REVIEW and role.evidence_json()["signals"]["ambiguous"]


# ================================================================ LLM fallback in the pipeline
def test_mock_llm_picks_only_among_candidates_and_is_reviewed(vocab, config, fake):
    llm = MockLLMClient(config.llm.llm, db=vocab)
    intel = JobIntelligence(vocab, config, embedder=fake, llm=llm)
    hit = skills_of(intel.analyze("Electrician", "MCB panel work."))["panel-wiring"]
    assert hit.method == ExtractionMethod.LLM and hit.decision == MatchDecision.REVIEW
    assert hit.confidence == config.scoring.skill_matching.llm_fallback_max_confidence
    assert hit.llm["provider"] == "mock" and hit.llm["ok"] is True


@pytest.mark.parametrize(
    "failure", ["this is not json", LlmCallError("HTTP 500"), TimeoutError("slow")]
)
def test_pipeline_survives_bad_or_failing_llm(vocab, config, fake, failure):
    settings = config.llm.llm.model_copy(update={"retry_backoff_seconds": 0.0})
    llm = MockLLMClient(
        settings, responses={"skill_match_fallback": failure, "role_match_fallback": failure}
    )
    analysis = JobIntelligence(vocab, config, embedder=fake, llm=llm).analyze(
        "Electrician", "House wiring and MCB panel work."
    )
    assert "electrical-wiring" in skills_of(analysis)  # the rules still work
    assert "panel-wiring" not in skills_of(analysis)  # no LLM answer, no LLM match
    assert analysis.llm_calls and all(call["ok"] is False for call in analysis.llm_calls)


# ================================================================ ingestion
def test_ingestion_keeps_provenance_and_marks_synthetic_rows(vocab, config, intel):
    data = csv_rows(
        row("EV Technician", "Battery diagnostics and charging station work."),
        row("Electrician", "House wiring.", source="S05", synthetic="false", sector="ELECTRICAL"),
    )
    report = ingest_postings_csv(vocab, config, data, file_name="test.csv", today=date(2026, 9, 30))
    assert (report.records_seen, report.records_imported, report.errors) == (2, 2, [])
    batch = process_batch(vocab, intel, posting_ids=report.posting_ids)
    assert batch.processed == 2 and batch.failed == 0
    synthetic, real = (vocab.get(JobPosting, i) for i in report.posting_ids)
    assert (synthetic.is_synthetic, synthetic.source, synthetic.license_note) == (True, "Y16", NOTE)
    assert synthetic.ingestion_run_id == report.ingestion_run_id and synthetic.quarter == "2026Q3"
    assert real.is_synthetic is False and real.source == "S05"
    for posting in (synthetic, real):
        links = list(
            vocab.scalars(select(PostingSkill).where(PostingSkill.posting_id == posting.id))
        )
        assert links and all(link.is_synthetic == posting.is_synthetic for link in links)
    out = posting_out(vocab, synthetic)
    assert out["roles"][0]["role_code"] == "ev-service-technician"
    first = out["skills"][0]
    assert first["evidence_kind"] == "OBSERVED" and first["source_record"]["source"] == "Y16"
    assert first["is_synthetic"] is True and first["evidence"]["span"]


def test_missing_description_invalid_dates_and_contact_details(vocab, config, intel):
    data = csv_rows(
        row("EV Charging Technician", ""),
        row("Wireman", "House wiring.", day="31/02/2026"),
        row("Wireman", "House wiring.", day="2027-01-01"),
        row("Electrician", "House wiring. Call 98765 43210 or hr@example.com", sector="ELECTRICAL"),
        row("Solar Installer", "Rooftop solar installation.", source=""),
    )
    report = ingest_postings_csv(vocab, config, data, file_name="t.csv", today=date(2026, 9, 30))
    assert report.records_imported == 2
    assert {(e.row, e.field) for e in report.errors} == {
        (3, "posted_date"),
        (4, "posted_date"),
        (6, "source"),
    }
    assert any(w.field == "description" and "no description" in w.message for w in report.warnings)
    electrician = vocab.get(JobPosting, report.posting_ids[1])
    assert "98765" not in electrician.description and "@" not in electrician.description
    process_batch(vocab, intel, posting_ids=report.posting_ids)
    charging = vocab.get(JobPosting, report.posting_ids[0])
    out = posting_out(vocab, charging)
    assert out["roles"][0]["role_code"] == "ev-charging-installer"
    assert {s["evidence_kind"] for s in out["skills"]} == {"INFERRED"}  # nothing observed


def test_duplicates_in_the_file_and_in_the_database(vocab, config):
    data = csv_rows(
        row("EV Technician", "Battery diagnostics."),
        row("EV  technician!", "Battery diagnostics, again.", day="2026-09-11"),  # same week
        row("EV Technician", "Battery diagnostics.", day="2026-09-21"),  # another week
    )
    first = ingest_postings_csv(vocab, config, data, file_name="d.csv", today=date(2026, 9, 30))
    assert (first.records_imported, len(first.duplicates)) == (2, 1)
    again = ingest_postings_csv(vocab, config, data, file_name="d.csv", today=date(2026, 9, 30))
    assert again.records_imported == 0 and len(again.duplicates) == 3
    assert sum("already in the database" in d.message for d in again.duplicates) == 2


def test_unknown_district_goes_to_review(vocab, config):
    data = csv_rows(
        row("Electrician", "House wiring.", district="").replace(
            '"Ambad MIDC, Nashik"', "Somewhere Estate"
        )
    )
    report = ingest_postings_csv(vocab, config, data, file_name="p.csv", today=date(2026, 9, 30))
    posting = vocab.get(JobPosting, report.posting_ids[0])
    assert posting.district_id is None
    kinds = set(
        vocab.scalars(select(ReviewItem.kind).where(ReviewItem.source_record_id == str(posting.id)))
    )
    assert kinds == {"PLACE_MAPPING"}


def test_unreadable_files_are_reported_not_crashed(vocab, config):
    report = ingest_postings_csv(vocab, config, b"name,city\nx,y\n", file_name="bad.csv")
    assert report.records_imported == 0 and "Missing required column" in report.errors[0].message
    report = ingest_postings_csv(
        vocab, config, "title\n\xff".encode("latin-1"), file_name="bad.csv"
    )
    assert "not UTF-8" in report.errors[0].message


# ================================================================ batch processing
def test_batch_processes_pending_postings_and_isolates_failures(vocab, config, intel, monkeypatch):
    data = csv_rows(
        *(
            row(title, "House wiring.", sector="ELECTRICAL")
            for title in ("Electrician", "Wireman", "Explode", "Electrician (ITI)")
        )
    )
    report = ingest_postings_csv(vocab, config, data, file_name="b.csv", today=date(2026, 9, 30))
    statuses = set(
        vocab.scalars(
            select(JobPosting.extraction_status).where(JobPosting.id.in_(report.posting_ids))
        )
    )
    assert statuses == {"PENDING"}
    real_analyze = intel.analyze

    def analyze(title, description, sector=None):
        if title == "Explode":
            raise RuntimeError("boom")
        return real_analyze(title, description, sector)

    monkeypatch.setattr(intel, "analyze", analyze)
    batch = process_batch(vocab, intel, posting_ids=report.posting_ids)
    assert (batch.selected, batch.processed, batch.failed) == (4, 3, 1)
    assert batch.skills_extracted >= 3 and batch.roles_matched == 3
    failed = vocab.scalar(select(JobPosting).where(JobPosting.title == "Explode"))
    assert failed.extraction_status == "FAILED" and "boom" in failed.extraction_error
    monkeypatch.setattr(intel, "analyze", real_analyze)
    retried = process_batch(vocab, intel, posting_ids=report.posting_ids, retry_failed=True)
    assert retried.processed == 1 and failed.extraction_status == "DONE"


def test_reprocessing_replaces_pipeline_links_but_keeps_human_ones(vocab, config, intel):
    report = ingest_postings_csv(
        vocab,
        config,
        csv_rows(row("Electrician", "House wiring.", sector="ELECTRICAL")),
        file_name="r.csv",
        today=date(2026, 9, 30),
    )
    posting = vocab.get(JobPosting, report.posting_ids[0])
    process_posting(vocab, intel, posting)
    earthing = synthetic_id("skill", "earthing")
    vocab.add(
        PostingSkill(
            posting_id=posting.id,
            skill_id=earthing,
            confidence=1.0,
            method="HUMAN",
            is_synthetic=True,
        )
    )
    vocab.flush()
    process_posting(vocab, intel, posting)
    methods = dict(
        vocab.execute(
            select(PostingSkill.skill_id, PostingSkill.method).where(
                PostingSkill.posting_id == posting.id
            )
        ).all()
    )
    assert methods[earthing] == "HUMAN" and len(methods) >= 2


# ================================================================ the synthetic dataset
def _load_synthetic_postings(db, export, config, count):
    """The vocabulary plus `count` synthetic postings (without a demo employer) and their
    ground-truth links."""
    postings = [p for p in export["job_posting"] if p["employer_id"] is None][::97][:count]
    ids = {p["id"] for p in postings}
    subset = vocabulary_only(export)
    subset["job_posting"] = postings
    subset["posting_role"] = [r for r in export["posting_role"] if r["posting_id"] in ids]
    subset["posting_skill"] = [r for r in export["posting_skill"] if r["posting_id"] in ids]
    load_dataset(db, subset, config)
    return postings, subset


def test_generator_ground_truth_is_never_overwritten(vocab, export, config, intel):
    postings, _ = _load_synthetic_postings(vocab, export, config, 2)
    posting = vocab.get(JobPosting, postings[0]["id"])
    with pytest.raises(GroundTruthConflict):
        process_posting(vocab, intel, posting)
    preview = process_posting(vocab, intel, posting, dry_run=True)
    assert preview.stored is False and preview.analysis.skills
    kinds = set(
        vocab.scalars(
            select(PostingSkill.evidence_kind).where(PostingSkill.posting_id == posting.id)
        )
    )
    assert kinds == {"SYNTHETIC"}  # generator links are labelled, and untouched


def test_pipeline_recovers_the_synthetic_ground_truth(vocab, export, config, intel):
    postings, subset = _load_synthetic_postings(vocab, export, config, 20)
    code = {r["id"]: r["code"] for r in export["skill"]}
    roles = {r["id"]: r["code"] for r in export["job_role"]}
    missed, wrong_roles = [], []
    for posting in postings:
        truth = {
            code[s["skill_id"]] for s in subset["posting_skill"] if s["posting_id"] == posting["id"]
        }
        role = next(
            roles[r["role_id"]] for r in subset["posting_role"] if r["posting_id"] == posting["id"]
        )
        analysis = intel.analyze(posting["title"], posting["description"])
        accepted = {h.skill.code for h in analysis.observed if h.decision == MatchDecision.ACCEPT}
        missed += sorted(truth - accepted)
        if analysis.role is None or analysis.role.role.code != role:
            wrong_roles.append((posting["title"], role))
    assert missed == [] and wrong_roles == []


def test_dedupe_key_is_shared_with_the_synthetic_generator(export):
    district = {r["id"]: r["code"] for r in export["district"]}
    for posting in export["job_posting"][:50]:
        key = posting_dedupe_key(
            posting["title"],
            posting["employer_name_raw"],
            district[posting["district_id"]],
            posting["posted_on"],
        )
        assert key == posting["dedupe_key"]


# ================================================================ small helpers
def test_places_languages_dates_and_contacts(vocab, config):
    places = DistrictResolver(vocab, config)
    assert places.resolve(None, "Satpur MIDC").code == "MH-NASHIK"
    assert places.resolve(None, "Chakan, Poona").code == "MH-PUNE"
    assert places.resolve("MH-KOLHAPUR", None).how == "code"
    assert places.resolve(None, "Nashik or Pune").code is None
    cues = load_cues()
    assert cues.detect_language("घरगुती वायरिंग आणि विद्युत सुरक्षा") == Language.MR
    assert cues.detect_language("बिजली वायरिंग और विद्युत सुरक्षा") == Language.HI
    assert cues.detect_language("House wiring") == Language.EN
    assert parse_date("12/09/2026") == date(2026, 9, 12) and parse_date("31/02/2026") is None
    assert scrub_contacts("Call +91 98765 43210 now")[1] == 1
    view = analyze_text("Hands-on EV diagnostics; 2-4 yrs.")
    assert [t.norm for t in view.tokens][:3] == ["hands", "on", "ev"] and len(view.segments) == 2


# ================================================================ API
@pytest.fixture
def admin(vocab):
    user = AppUser(
        email=f"admin-{uuid.uuid4().hex[:6]}@example.org",
        password_hash=FAKE_ARGON2_HASH,
        display_name="Admin",
        role="admin",
    )
    vocab.add(user)
    vocab.flush()
    token, _ = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api_intel(api, monkeypatch, vocab, config, fake):
    """API endpoints use the fake embedder and no LLM instead of the configured ones."""
    monkeypatch.setattr(
        JobIntelligence,
        "create",
        classmethod(lambda cls, db, cfg: cls(db, cfg, embedder=fake, llm=None)),
    )
    return api


def test_api_ingests_processes_and_explains(api_intel, admin, vocab):
    api = api_intel
    body = csv_rows(
        row(
            "EV Technician",
            "EV technician required with battery diagnostics and charging station experience.",
        )
    )
    response = api.post(
        "/api/v1/ingestion/job-postings?file_name=api.csv",
        content=body,
        headers={**admin, "Content-Type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert (report["records_imported"], report["processed"], report["roles_matched"]) == (1, 1, 1)
    assert report["skills_extracted"] == 2
    posting_id = report["posting_ids"][0]
    detail = api.get(f"/api/v1/ingestion/job-postings/{posting_id}", headers=admin).json()
    assert detail["roles"][0]["role_code"] == "ev-service-technician"
    assert {s["skill_code"]: s["evidence_kind"] for s in detail["skills"]} == {
        "battery-management": "OBSERVED",
        "ev-charging-systems": "OBSERVED",
        "ev-diagnostics": "INFERRED",
        "hv-safety": "INFERRED",
    }
    rerun = api.post(
        f"/api/v1/ingestion/job-postings/{posting_id}/process?dry_run=true", headers=admin
    ).json()
    assert rerun["stored"] is False and rerun["role"]["role_code"] == "ev-service-technician"


def test_api_reads_server_files_only_under_data(api_intel, admin):
    ok = api_intel.post(
        "/api/v1/ingestion/job-postings?process=false",
        json={"path": "data/synthetic/job_postings_sample.csv"},
        headers=admin,
    )
    assert ok.status_code == 200 and ok.json()["records_imported"] >= 10
    for path in ("../README.md", "config/scoring.yaml", "backend/app/main.py"):
        response = api_intel.post(
            "/api/v1/ingestion/job-postings", json={"path": path}, headers=admin
        )
        assert response.status_code == 400, path


def test_api_protects_ground_truth_and_needs_admin(
    api_intel, admin, vocab, export, config, db_session
):
    postings, _ = _load_synthetic_postings(vocab, export, config, 1)
    conflict = api_intel.post(
        f"/api/v1/ingestion/job-postings/{postings[0]['id']}/process", headers=admin
    )
    assert (
        conflict.status_code == 409
        and conflict.json()["detail"]["code"] == "SYNTHETIC_GROUND_TRUTH"
    )
    candidate = AppUser(
        email="cand@example.org", password_hash=FAKE_ARGON2_HASH, display_name="C", role="candidate"
    )
    db_session.add(candidate)
    db_session.flush()
    token, _ = create_access_token(candidate.id, candidate.role)
    denied = api_intel.post(
        "/api/v1/ingestion/job-postings/process-batch", headers={"Authorization": f"Bearer {token}"}
    )
    assert denied.status_code == 403
    missing = api_intel.get(f"/api/v1/ingestion/job-postings/{uuid.uuid4()}", headers=admin)
    assert missing.status_code == 404


def test_api_batch_endpoint(api_intel, admin, vocab, config):
    ingest_postings_csv(
        vocab,
        config,
        csv_rows(row("Wireman", "House wiring.", sector="ELECTRICAL")),
        file_name="x.csv",
        today=date(2026, 9, 30),
    )
    vocab.flush()
    result = api_intel.post(
        "/api/v1/ingestion/job-postings/process-batch?limit=10", headers=admin
    ).json()
    assert result["processed"] >= 1 and result["failed"] == 0
    pending = vocab.scalar(
        select(func.count())
        .select_from(JobPosting)
        .where(JobPosting.extraction_status == "PENDING")
    )
    assert pending == 0
    assert vocab.scalar(select(func.count()).select_from(PostingRole)) >= 1


def test_llm_disabled_config_still_runs(vocab, config, fake):
    off = dataclasses.replace(
        config,
        llm=config.llm.model_copy(
            update={"llm": config.llm.llm.model_copy(update={"mode": "off"})}
        ),
    )
    intel = JobIntelligence.create(vocab, off)
    assert intel.llm is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Age 18-35 years. Solar panel installation.", None),
        ("उम्र 18-35 साल", None),
        ("We are a 25 years old company. House wiring work.", None),
        ("Salary 15000 per month, 2 years bond.", None),
        ("Age 18-35 years, 2 years experience in wiring", (2.0, None)),
        ("Need electrician. 2-4 years experience.", (2.0, 4.0)),
        ("अनुभव - 1-2 वर्षे", (1.0, 2.0)),
    ],
)
def test_only_experience_years_count_as_experience(text, expected):
    """Age limits, bonds and company age are not years of experience (review finding)."""
    assert first_years(text) == expected
