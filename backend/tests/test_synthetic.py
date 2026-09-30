"""Tests for the synthetic demo dataset (app/synthetic): determinism, honesty rules, the
planted patterns, the CSV export and the database import.

The pattern tests recompute each pattern from the generated rows with the thresholds in
config/scoring.yaml, so they fail if the data stops containing the pattern.
"""

import copy
import hashlib
import uuid
from pathlib import Path

import pytest
import yaml
from sqlalchemy import func, select

from app.cli.synthetic import main as synthetic_cli
from app.config import load_config
from app.core.settings import REPO_ROOT, Settings
from app.models import AppUser, District, IngestionRun, Institute, JobPosting, Skill
from app.models.enums import MismatchStatus, TrendStatus
from app.synthetic.checks import run_checks
from app.synthetic.export import ExportError, read_export, staleness, table_csv, write_export
from app.synthetic.generator import generate
from app.synthetic.ids import synthetic_id
from app.synthetic.loader import (
    LoadError,
    differences,
    load_dataset,
    read_dataset,
    unmarked_rows,
)
from app.synthetic.metrics import World
from app.synthetic.spec import SpecError, check_spec_against_config, load_spec
from app.synthetic.tables import BY_NAME, SYNTHETIC_TABLES

FAKE_ARGON2_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdA"


@pytest.fixture(scope="module")
def config():
    # Ignore SYNTH_SEED / .env overrides: the committed export uses the seed in the YAML.
    return load_config(settings=Settings(_env_file=None, synth_seed=None))


@pytest.fixture(scope="module")
def spec(config):
    return load_spec(REPO_ROOT / config.synthetic.spec_file)


@pytest.fixture(scope="module")
def dataset(config, spec):
    return generate(config, spec)


@pytest.fixture(scope="module")
def world(dataset, config):
    return World(dataset, config)


def failures(results) -> list[str]:
    return [
        f"{r.id}: {line}"
        for r in results
        if r.passed is False
        for line in r.details
        if "[FAIL]" in line
    ]


def write(dataset, directory: Path, config, spec, seed: int) -> None:
    write_export(
        dataset,
        directory,
        config,
        seed=seed,
        spec_file=config.synthetic.spec_file,
        spec_sha256="0" * 64,
        generated_at=spec.generated_at,
        as_of=spec.as_of,
    )


# ---------------------------------------------------------------- spec and determinism
def test_spec_is_valid_and_fits_the_configuration(config, spec):
    assert check_spec_against_config(spec, config) == []


def test_same_seed_gives_byte_identical_exports(tmp_path, config, spec):
    write(generate(config, spec), tmp_path / "a", config, spec, config.synthetic.seed)
    write(generate(config, spec), tmp_path / "b", config, spec, config.synthetic.seed)
    files = sorted(p.name for p in (tmp_path / "a").iterdir())
    assert len(files) == len(SYNTHETIC_TABLES) + 1  # + manifest.json
    for name in files:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name


def test_committed_export_matches_the_generator(config, dataset):
    """data/synthetic/export must be regenerated whenever the spec or generator changes."""
    manifest_dir = REPO_ROOT / config.synthetic.export_dir
    _, manifest = read_export(manifest_dir, config)
    assert manifest["seed"] == config.synthetic.seed
    for entry in manifest["files"]:
        expected = hashlib.sha256(table_csv(entry["table"], dataset[entry["table"]])).hexdigest()
        assert (
            entry["sha256"] == expected
        ), f"{entry['file']} is out of date: run python -m app.cli.synthetic generate"


@pytest.mark.parametrize("seed", [1, 2, 99])
def test_other_seeds_change_details_but_keep_every_pattern(config, spec, dataset, seed):
    other = generate(config, spec, seed=seed)
    assert failures(run_checks(other, config, spec)) == []
    assert len(other["job_posting"]) == len(dataset["job_posting"])
    assert [r["title"] for r in other["job_posting"]] != [
        r["title"] for r in dataset["job_posting"]
    ]


def test_all_checks_pass_on_the_generated_dataset(dataset, config, spec):
    results = run_checks(dataset, config, spec)
    assert failures(results) == []
    ids = {r.id for r in results}
    assert {"DATA-1", "DATA-2", "PP1", "PP2", "PP3", "PP4", "PP5", "PP6", "PP7", "CTRL-1"} <= ids
    assert all(r.status == "PASS" for r in results)


# ---------------------------------------------------------------- honesty
def test_every_synthetic_record_is_marked_and_has_provenance(dataset, config):
    for info in SYNTHETIC_TABLES:
        rows = dataset[info.name]
        assert rows, info.name
        assert all(r["is_synthetic"] is True for r in rows), info.name
        if info.has_source:
            source = getattr(config.synthetic.source_ids, info.dataset)
            assert {r["source"] for r in rows} == {source}, info.name
            assert all("seed" in r["source_ref"] and r["fetched_at"] is not None for r in rows)
            assert all(r["license_note"].startswith("SYNTHETIC") for r in rows)
    # Config sectors/districts are not synthetic and not official-coded by the generator.
    assert all(not r["is_synthetic"] for t in ("sector", "district") for r in dataset[t])
    assert all(r["official_code"] is None for r in dataset["district"])


def test_no_official_codes_and_only_fictional_names(dataset):
    for table in ("job_role", "course", "institute"):
        assert all(
            r["official_code"] is None and not r["official_code_verified"] for r in dataset[table]
        )
    assert all(r["name"].startswith("Example ") for r in dataset["institute"] + dataset["employer"])
    assert all(r["employer_name_raw"].startswith("Example ") for r in dataset["job_posting"])
    assert all(r["is_simulated"] and r["citation_url"] is None for r in dataset["sector_event"])


# ---------------------------------------------------------------- planted patterns
def test_nashik_ev_demand_grows(world):
    ev = world.sector_postings("EV", "MH-NASHIK")
    assert all(later > earlier for earlier, later in zip(ev, ev[1:], strict=False)), ev
    assert sum(ev[3:]) > 2 * sum(ev[:3])  # the last half-year-and-a-bit is far above the first
    for skill in ("ev-diagnostics", "battery-management", "ev-charging-systems"):
        trend = world.trend(world.skill_mentions("MH-NASHIK")[skill])
        assert trend.status == TrendStatus.EMERGING, trend.describe()


def test_nashik_ev_roles_are_undersupplied(world):
    for role in ("ev-service-technician", "ev-charging-installer"):
        assert world.mismatch(role, "MH-NASHIK")[1] == MismatchStatus.UNDERSUPPLIED


def test_nashik_electrician_course_has_low_ev_skill_coverage(world, config):
    taught = world.taught["demo-electrician"]
    assert world.course_modules["demo-electrician"] == [
        "Electrical Wiring",
        "Electrical Safety",
        "Basic Motors",
        "Motor Rewinding",
    ]
    for skill in ("ev-diagnostics", "battery-management", "ev-charging-systems"):
        assert skill not in taught
    coverage = world.coverage(
        "demo-electrician", "ev-service-technician", world.emerging_skills("MH-NASHIK")
    )
    assert coverage < config.scoring.course_health.flags.outdated_coverage_below


def test_kolhapur_wireman_is_oversupplied_with_weak_placement(world, config):
    postings = world.role_postings("MH-KOLHAPUR")["wireman"]
    assert postings[-1] < postings[0]
    ratio, status = world.mismatch("wireman", "MH-KOLHAPUR")
    assert status == MismatchStatus.OVERSUPPLIED
    assert ratio > config.scoring.mismatch.oversupplied_above
    for (institute, course), (completed, placed) in world.placement_rates().items():
        if course == "demo-wireman" and world.institute_district[institute] == "MH-KOLHAPUR":
            assert placed / completed < config.scoring.course_health.flags.low_placement_rate_below


def test_motor_rewinding_declines_over_four_quarters(world, config):
    window = config.scoring.trend.window_quarters
    q1, q2, q3, q4 = world.skill_mentions()["motor-rewinding"][-window:]
    assert q1 > q2 > q3 > q4
    trend = world.trend(world.skill_mentions()["motor-rewinding"])
    assert trend.status == TrendStatus.DECLINING, trend.describe()


def test_nashik_ev_event_lifts_future_demand(world, config):
    event = next(
        r
        for r in world.data["sector_event"]
        if r["id"] == synthetic_id("sector_event", "nashik-ev-battery-unit")
    )
    uplift = world.event_uplift(event)
    impact = config.scoring.event_impact
    assert len(uplift) == impact.lag_end_quarter - impact.lag_start_quarter + 1
    assert set(uplift) & set(world.forecast_quarters())
    assert sum(sum(v.values()) for v in uplift.values()) == pytest.approx(600 * 0.6)


def test_employer_surveys_ask_for_more_ev_people(world):
    for district in ("MH-NASHIK", "MH-PUNE"):
        headcount = world.survey_headcount("EV", district)
        assert all(b > a for a, b in zip(headcount, headcount[1:], strict=False)), headcount


def test_ev_training_places_best_and_absorption_is_computable(world):
    rates = world.placement_rates()
    ev_centre = [p / c for (i, _), (c, p) in rates.items() if i == "EX-TC-E"]
    others = [p / c for (i, _), (c, p) in rates.items() if i != "EX-TC-E"]
    assert min(ev_centre) > max(others)  # every EV-centre course beats every other course
    absorption = world.absorption()
    assert {d for _, d in absorption} == {"MH-NASHIK", "MH-PUNE", "MH-NAGPUR", "MH-KOLHAPUR"}
    for placed, completers in absorption.values():
        assert 0 <= placed <= completers


# ---------------------------------------------------------------- the validator is not blind
def _without_postings(dataset, predicate):
    broken = dict(dataset)
    dropped = {r["id"] for r in dataset["job_posting"] if predicate(r)}
    for table in ("job_posting", "posting_role", "posting_skill"):
        key = "id" if table == "job_posting" else "posting_id"
        broken[table] = [r for r in dataset[table] if r[key] not in dropped]
    return broken


def _failed(dataset, config, spec) -> set[str]:
    return {r.id for r in run_checks(dataset, config, spec) if r.passed is False}


def test_validator_catches_an_unmarked_row(dataset, config, spec):
    broken = dict(dataset)
    broken["candidate"] = [dict(r) for r in dataset["candidate"]]
    broken["candidate"][0]["is_synthetic"] = False
    assert "DATA-1" in _failed(broken, config, spec)


def test_validator_catches_missing_ev_growth(dataset, config, spec):
    nashik = synthetic_id("district", "MH-NASHIK")
    ev_roles = {
        synthetic_id("job_role", "ev-service-technician"),
        synthetic_id("job_role", "ev-charging-installer"),
    }
    ev_postings = {r["posting_id"] for r in dataset["posting_role"] if r["role_id"] in ev_roles}
    broken = _without_postings(
        dataset,
        lambda r: r["id"] in ev_postings
        and r["district_id"] == nashik
        and r["quarter"] == "2026Q3",
    )
    assert "PP1" in _failed(broken, config, spec)


def test_validator_catches_a_flat_motor_rewinding_trend(dataset, config, spec):
    rewinding = synthetic_id("skill", "motor-rewinding")
    extra = [
        {**link, "skill_id": rewinding, "matched_text": "rewinding"}
        for link in dataset["posting_skill"]
        if link["skill_id"] == synthetic_id("skill", "electrical-wiring")
        and link["posting_id"]
        in {r["id"] for r in dataset["job_posting"] if r["quarter"] == "2026Q3"}
    ][:20]
    broken = dict(dataset)
    broken["posting_skill"] = dataset["posting_skill"] + extra
    assert "PP4" in _failed(broken, config, spec)


def test_validator_catches_an_ev_module_in_the_nashik_course(dataset, config, spec):
    module = synthetic_id("course_module", "demo-electrician", 1)
    broken = dict(dataset)
    broken["module_skill"] = dataset["module_skill"] + [
        {
            **dataset["module_skill"][0],
            "module_id": module,
            "skill_id": synthetic_id("skill", skill),
            "band_taught": 3,
        }
        for skill in ("ev-diagnostics", "battery-management", "ev-charging-systems")
    ]
    assert "PP2" in _failed(broken, config, spec)


def test_validator_catches_balanced_kolhapur_wireman_supply(dataset, config, spec):
    kolhapur_wireman = {
        synthetic_id("course_offering", institute, "demo-wireman", year)
        for institute in ("EX-ITI-J", "EX-ITI-K")
        for year in ("2024-25", "2025-26")
    }
    broken = dict(dataset)
    broken["course_offering"] = [
        {**r, "seats_filled": 20} if r["id"] in kolhapur_wireman else r
        for r in dataset["course_offering"]
    ]
    assert "PP3" in _failed(broken, config, spec)


# ---------------------------------------------------------------- spec errors
def _spec_file(tmp_path: Path, change) -> Path:
    raw = yaml.safe_load(
        (REPO_ROOT / "data/synthetic/spec/demo_world.yaml").read_text(encoding="utf-8")
    )
    change(raw)
    path = tmp_path / "world.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return path


def test_spec_rejects_an_unknown_skill(tmp_path):
    path = _spec_file(
        tmp_path, lambda raw: raw["roles"][0]["skills"][0].update(skill="no-such-skill")
    )
    with pytest.raises(SpecError, match="unknown skill 'no-such-skill'"):
        load_spec(path)


def test_spec_rejects_an_alias_used_by_two_skills(tmp_path):
    def duplicate(raw):
        raw["skills"][1]["aliases"]["en"].append(raw["skills"][0]["aliases"]["en"][0])

    with pytest.raises(SpecError, match="aliases must be unique per language"):
        load_spec(_spec_file(tmp_path, duplicate))


def test_spec_rejects_a_schedule_of_the_wrong_length(tmp_path, config):
    path = _spec_file(
        tmp_path, lambda raw: raw["posting_schedule"]["MH-NASHIK"]["electrician"].pop()
    )
    problems = check_spec_against_config(load_spec(path), config)
    assert any("posting_schedule.MH-NASHIK.electrician has 5 values" in p for p in problems)


def test_spec_rejects_too_few_postings(tmp_path, config):
    def shrink(raw):
        for schedule in raw["posting_schedule"].values():
            schedule["electrician"] = [1] * 6

    problems = check_spec_against_config(load_spec(_spec_file(tmp_path, shrink)), config)
    assert any("postings; target 2000" in p for p in problems)


# ---------------------------------------------------------------- export
def test_export_round_trip_keeps_every_value(tmp_path, dataset, config, spec):
    write(dataset, tmp_path, config, spec, config.synthetic.seed)
    loaded, manifest = read_export(tmp_path, config)
    assert manifest["is_synthetic"] is True
    for info in SYNTHETIC_TABLES:
        assert loaded[info.name] == dataset[info.name], info.name


def test_edited_export_is_refused(tmp_path, dataset, config, spec):
    write(dataset, tmp_path, config, spec, config.synthetic.seed)
    path = tmp_path / "job_posting.csv"
    path.write_text(
        path.read_text(encoding="utf-8").replace("2026Q3", "2026Q2", 1), encoding="utf-8"
    )
    with pytest.raises(ExportError, match="does not match"):
        read_export(tmp_path, config)


def test_cli_generates_and_validates_an_export(tmp_path, capsys):
    assert synthetic_cli(["check-spec"]) == 0
    assert synthetic_cli(["generate", "--seed", "5", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "manifest.json").is_file() and (tmp_path / "summary.json").is_file()
    assert synthetic_cli(["validate", "--source", "export", "--from", str(tmp_path)]) == 0
    assert "All checks passed." in capsys.readouterr().out


# ---------------------------------------------------------------- database import
@pytest.mark.db
def test_load_matches_the_dataset_and_passes_validation(db_session, dataset, config, spec):
    report = load_dataset(db_session, dataset, config)
    assert report.written["job_posting"] == len(dataset["job_posting"])
    stored = read_dataset(db_session, config)
    assert differences(dataset, stored) == []
    assert failures(run_checks(stored, config, spec)) == []  # includes ingestion_run_id checks
    runs = db_session.scalars(
        select(IngestionRun).where(IngestionRun.id.in_(report.runs.values()))
    ).all()
    assert {r.source for r in runs} == set(config.synthetic.source_ids.model_dump().values())
    assert all(r.status == "SUCCEEDED" and r.rows_loaded > 0 for r in runs)


@pytest.mark.db
def test_reloading_is_idempotent_and_keeps_links_to_demo_entities(db_session, dataset, config):
    load_dataset(db_session, dataset, config)
    example_iti = synthetic_id("institute", "EX-ITI-A")
    db_session.add(
        AppUser(
            email="admin.iti.a@example.org",
            password_hash=FAKE_ARGON2_HASH,
            display_name="Demo admin",
            role="institute_admin",
            institute_id=example_iti,
        )
    )
    db_session.flush()
    report = load_dataset(db_session, dataset, config)
    # Nothing is stale on a reload (link rows are always replaced, so they do not count).
    assert all(n == 0 for name, n in report.deleted.items() if not BY_NAME[name].is_link)
    assert db_session.scalar(select(func.count()).select_from(JobPosting)) == len(
        dataset["job_posting"]
    )
    user = db_session.scalar(select(AppUser).where(AppUser.email == "admin.iti.a@example.org"))
    assert user is not None and user.institute_id == example_iti
    assert differences(dataset, read_dataset(db_session, config)) == []


@pytest.mark.db
def test_reloading_with_another_seed_replaces_the_rows(db_session, dataset, config, spec):
    load_dataset(db_session, dataset, config)
    other = generate(config, spec, seed=3)
    report = load_dataset(db_session, other, config)
    assert report.deleted["placement_outcome"] > 0  # different trainees were placed
    assert differences(other, read_dataset(db_session, config)) == []


@pytest.mark.db
def test_loading_never_overwrites_real_data(db_session, dataset, config):
    db_session.add(
        Skill(
            code="ev-diagnostics",
            name="EV Diagnostics (curated)",
            skill_type="TECHNICAL",
            source="S18",
        )
    )
    db_session.flush()
    with pytest.raises(LoadError, match="skill: 1 non-synthetic rows already use the same code"):
        load_dataset(db_session, dataset, config)
    assert db_session.scalar(select(func.count()).select_from(Institute)) == 0
    assert db_session.scalar(select(func.count()).select_from(District)) == 0


@pytest.mark.db
def test_existing_districts_are_reused_not_changed(db_session, dataset, config):
    real_id = uuid.uuid4()
    db_session.add(
        District(
            id=real_id,
            code="MH-NASHIK",
            name="Nashik",
            state_name="Maharashtra",
            source="S01",
            aliases=["Nasik"],
        )
    )
    db_session.flush()
    report = load_dataset(db_session, dataset, config)
    assert report.reference_created["district"] == len(config.scope.districts) - 1
    institute = db_session.scalar(select(Institute).where(Institute.code == "EX-ITI-A"))
    assert institute.district_id == real_id
    district = db_session.get(District, real_id)
    assert district.source == "S01" and not district.is_synthetic
    assert differences(dataset, read_dataset(db_session, config)) == []


def test_deep_copies_are_not_needed_by_checks(dataset, config, spec):
    """run_checks must not modify the dataset it is given."""
    before = copy.deepcopy(dataset["course_offering"])
    run_checks(dataset, config, spec)
    assert dataset["course_offering"] == before


# ---------------------------------------------------------------- more blind-spot checks
def _replace_rows(dataset, table, change):
    broken = dict(dataset)
    broken[table] = [change(dict(r)) for r in dataset[table]]
    return broken


def test_validator_catches_an_event_in_the_wrong_district(dataset, config, spec):
    pune = synthetic_id("district", "MH-PUNE")
    event = synthetic_id("sector_event", spec.pattern_targets.event)
    broken = _replace_rows(
        dataset, "sector_event", lambda r: {**r, "district_id": pune} if r["id"] == event else r
    )
    assert "PP5" in _failed(broken, config, spec)


def test_validator_catches_weak_placement_at_the_ev_centre(dataset, config, spec):
    ev_centre = synthetic_id("institute", "EX-TC-E")
    offerings = {r["id"] for r in dataset["course_offering"] if r["institute_id"] == ev_centre}
    enrollments = {r["id"] for r in dataset["enrollment"] if r["course_offering_id"] in offerings}

    def unplace(r):
        if r["enrollment_id"] in enrollments:
            fields = ("placement_type", "employer_id", "role_id", "salary_monthly_inr", "placed_on")
            return {**r, "placed": False, **dict.fromkeys(fields)}
        return r

    assert "PP6" in _failed(_replace_rows(dataset, "placement_outcome", unplace), config, spec)


def test_validator_catches_flat_employer_demand(dataset, config, spec):
    def flatten(r):
        return {**r, "roles_json": [{**need, "count": 1} for need in r["roles_json"]]}

    assert "PP7" in _failed(
        _replace_rows(dataset, "employer_survey_response", flatten), config, spec
    )


def test_validator_catches_missing_provenance_and_invented_codes(dataset, config, spec):
    first = dataset["institute"][0]["id"]
    broken = _replace_rows(
        dataset, "institute", lambda r: {**r, "license_note": None} if r["id"] == first else r
    )
    assert "DATA-2" in _failed(broken, config, spec)
    coded = _replace_rows(
        dataset,
        "job_role",
        lambda r: {**r, "official_code": "7411.0100"} if r["code"] == "electrician" else r,
    )
    assert "DATA-3" in _failed(coded, config, spec)


def test_validator_catches_unrealistic_employers(dataset, config, spec):
    unwilling = synthetic_id("employer", "EX-EMP-NSK-05")  # answers NO to apprentices
    broken = _replace_rows(
        dataset,
        "placement_outcome",
        lambda r: {**r, "employer_id": unwilling} if r["placement_type"] == "APPRENTICESHIP" else r,
    )
    assert "DATA-5" in _failed(broken, config, spec)


@pytest.mark.parametrize(
    "change, message",
    [
        (
            lambda raw: raw["institutes"][0]["offerings"][0]["cohorts"].update(
                {"2026-27": {"filled": 10, "completion": 0.8, "placement": 0.5}}
            ),
            "ends after as_of",
        ),
        (
            lambda raw: raw["sector_events"][0].update(announced_on="2026-12-01"),
            "announced after as_of",
        ),
        (
            lambda raw: raw["employers"][0]["survey_skills"].update({"ev-diagnostics": "2027Q1"}),
            "starts outside the history",
        ),
        (lambda raw: raw["institutes"][0]["offerings"][0].update(seats=500), "seats out of range"),
        (
            lambda raw: raw["courses"][0].update(sector="EV"),
            "primary role electrician is in ELECTRICAL",
        ),
        (
            lambda raw: raw["pattern_targets"]["oversupply"].update(district="MH-PUNE"),
            "is not in PP3 districts",
        ),
        (
            lambda raw: raw["employers"][0]["survey_roles"].update({"motor-rewinder": [1, 1]})
            or raw["posting_schedule"]["MH-NASHIK"].pop("motor-rewinder")
            and None,
            "posting_schedule has no motor-rewinder ads",
        ),
    ],
)
def test_spec_rules_that_need_the_configuration(tmp_path, config, change, message):
    problems = check_spec_against_config(load_spec(_spec_file(tmp_path, change)), config)
    assert any(message in p for p in problems), problems


def test_spec_refuses_repeated_yaml_keys(tmp_path):
    text = (REPO_ROOT / "data/synthetic/spec/demo_world.yaml").read_text(encoding="utf-8")
    path = tmp_path / "world.yaml"
    path.write_text(text + '\nas_of: "2026-09-01"\n', encoding="utf-8")
    with pytest.raises(SpecError, match="appears twice"):
        load_spec(path)


def test_pseudonyms_are_stable_per_cohort(config, spec, dataset):
    raw = spec.model_dump(by_alias=True)
    raw["institutes"][0]["offerings"][0]["cohorts"]["2024-25"]["filled"] -= 1
    smaller = generate(config, type(spec).model_validate(raw))
    before = {r["pseudonym"] for r in dataset["candidate"]}
    after = {r["pseudonym"] for r in smaller["candidate"]}
    assert before - after == {"C-ITI-A-electrician-2024-058"}  # only that cohort's last person


# ---------------------------------------------------------------- export safety
def test_export_refuses_a_folder_that_is_not_an_export(tmp_path, dataset, config, spec):
    (tmp_path / "my_notes.csv").write_text("keep me", encoding="utf-8")
    with pytest.raises(ExportError, match="not an export folder"):
        write(dataset, tmp_path, config, spec, config.synthetic.seed)
    assert (tmp_path / "my_notes.csv").read_text(encoding="utf-8") == "keep me"


def test_damaged_manifest_is_a_clear_error(tmp_path, dataset, config, spec):
    write(dataset, tmp_path, config, spec, config.synthetic.seed)
    (tmp_path / "manifest.json").write_text("<<<<<<< HEAD", encoding="utf-8")
    with pytest.raises(ExportError, match="damaged"):
        read_export(tmp_path, config)


def test_out_of_date_export_is_detected(tmp_path, config):
    manifest = {"spec_sha256": "0" * 64, "generator_version": "0"}
    problems = staleness(manifest, REPO_ROOT / config.synthetic.spec_file)
    assert len(problems) == 2 and "spec changed" in problems[0]
    _, current = read_export(REPO_ROOT / config.synthetic.export_dir, config)
    assert staleness(current, REPO_ROOT / config.synthetic.spec_file) == []


def test_all_command_has_no_separate_input_folder():
    with pytest.raises(SystemExit):
        synthetic_cli(["all", "--from", "somewhere"])


# ---------------------------------------------------------------- loader safety
@pytest.mark.db
def test_loader_refuses_to_delete_rows_that_real_data_uses(db_session, dataset, config, spec):
    load_dataset(db_session, dataset, config)
    person = dataset["candidate"][-1]
    db_session.add(
        AppUser(
            email="learner@example.org",
            password_hash=FAKE_ARGON2_HASH,
            display_name="Learner",
            role="candidate",
            candidate_id=person["id"],
        )
    )
    db_session.flush()
    smaller = dict(dataset)
    for table, key in (("candidate", "id"), ("candidate_skill", "candidate_id")):
        smaller[table] = [r for r in dataset[table] if r[key] != person["id"]]
    gone = {r["id"] for r in dataset["enrollment"] if r["candidate_id"] == person["id"]}
    smaller["enrollment"] = [r for r in dataset["enrollment"] if r["id"] not in gone]
    outcomes = {r["id"] for r in dataset["placement_outcome"] if r["enrollment_id"] in gone}
    smaller["placement_outcome"] = [
        r for r in dataset["placement_outcome"] if r["id"] not in outcomes
    ]
    smaller["employer_rating"] = [
        r for r in dataset["employer_rating"] if r["placement_outcome_id"] not in outcomes
    ]
    with pytest.raises(LoadError, match="app_user row"):
        load_dataset(db_session, smaller, config)
    user = db_session.scalar(select(AppUser).where(AppUser.email == "learner@example.org"))
    assert user.candidate_id == person["id"]


@pytest.mark.db
def test_renaming_a_skill_clears_its_old_embedding(db_session, dataset, config):
    from app.nlp.skill_embeddings import embed_vocabulary
    from tests.helpers import FakeEmbedder

    load_dataset(db_session, dataset, config)
    embed_vocabulary(db_session, FakeEmbedder())
    renamed = dict(dataset)
    renamed["skill"] = [
        {**r, "name": "EV Fault Finding"} if r["code"] == "ev-diagnostics" else r
        for r in dataset["skill"]
    ]
    load_dataset(db_session, renamed, config)
    db_session.expire_all()
    changed = db_session.scalar(select(Skill).where(Skill.code == "ev-diagnostics"))
    untouched = db_session.scalar(select(Skill).where(Skill.code == "earthing"))
    assert changed.embedding is None and changed.embedding_model is None
    assert untouched.embedding is not None


@pytest.mark.db
def test_database_validation_sees_rows_that_lost_their_flag(db_session, dataset, config):
    from sqlalchemy import update

    load_dataset(db_session, dataset, config)
    assert set(unmarked_rows(db_session, config).values()) == {0}
    db_session.execute(
        update(Institute).where(Institute.code == "EX-ITI-A").values(is_synthetic=False)
    )
    assert unmarked_rows(db_session, config)["institute"] == 1
