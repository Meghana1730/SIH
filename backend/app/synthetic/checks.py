"""Validation of a synthetic dataset: honesty rules and the planted patterns.

    results = run_checks(dataset, config, spec)
    all(r.passed is not False for r in results)

Every check recomputes its numbers from the data itself (never from the spec's schedules)
with the thresholds in config/scoring.yaml, so a check fails if the data does not really
contain the pattern. Checks for patterns switched off in config/synthetic.yaml are skipped.

Mapping to the team's pattern list: P1 Nashik EV growth = PP1 + PP5 (event), P2 course gap
= PP2, P3 Kolhapur oversupply = PP3, P4 motor rewinding = PP4, P5 employer demand = PP7,
P6 placement outcomes = PP6, P7 evidence = DATA-1 / DATA-2.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.config import ProductConfig
from app.models.enums import EnrollmentStatus, ExtractionMethod, MismatchStatus, TrendStatus
from app.synthetic.generator import Dataset
from app.synthetic.ids import synthetic_id
from app.synthetic.metrics import IST, World
from app.synthetic.spec import WorldSpec
from app.synthetic.tables import SYNTHETIC_TABLES
from app.synthetic.timeline import quarter_of, quarter_start


@dataclass
class CheckResult:
    id: str
    title: str
    passed: bool | None  # None = skipped (pattern switched off)
    details: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return "SKIP" if self.passed is None else "PASS" if self.passed else "FAIL"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "details": self.details,
            "metrics": self.metrics,
        }


class _Check:
    """Collects expectations; the check passes only if every expectation holds."""

    def __init__(self, check_id: str, title: str) -> None:
        self.result = CheckResult(check_id, title, True)

    def expect(self, condition: bool, message: str) -> bool:
        self.result.details.append(f"[{'ok' if condition else 'FAIL'}] {message}")
        if not condition:
            self.result.passed = False
        return condition

    def note(self, message: str) -> None:
        self.result.details.append(f"[info] {message}")

    def metric(self, key: str, value: Any) -> None:
        self.result.metrics[key] = value


def strictly_increasing(series: list[int]) -> bool:
    return all(b > a for a, b in zip(series, series[1:], strict=False))


def strictly_decreasing(series: list[int]) -> bool:
    return all(b < a for a, b in zip(series, series[1:], strict=False))


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


# --------------------------------------------------------------------------- data checks
def check_marking(world: World, config: ProductConfig, spec: WorldSpec) -> CheckResult:
    check = _Check("DATA-1", "Every synthetic record is marked is_synthetic = true")
    total = 0
    for info in SYNTHETIC_TABLES:
        rows = world.data[info.name]
        total += len(rows)
        unmarked = sum(1 for r in rows if r["is_synthetic"] is not True)
        check.expect(
            bool(rows) and unmarked == 0,
            f"{info.name}: {len(rows)} rows, {unmarked} not marked synthetic",
        )
    reference = sum(1 for t in ("sector", "district") for r in world.data[t] if r["is_synthetic"])
    check.expect(reference == 0, "sector/district rows are configuration data, not synthetic")
    check.metric("synthetic_rows", total)
    return check.result


def check_provenance(world: World, config: ProductConfig, spec: WorldSpec) -> CheckResult:
    check = _Check("DATA-2", "Every synthetic record carries provenance (source, seed, license)")
    source_ids = config.synthetic.source_ids
    seeds: set[str] = set()
    for info in SYNTHETIC_TABLES:
        rows = world.data[info.name]
        if info.has_source:
            expected = getattr(source_ids, info.dataset)
            bad = 0
            for r in rows:
                seeds.update(re.findall(r"seed (\d+)", r["source_ref"] or ""))
                if (
                    r["source"] != expected
                    or "seed" not in (r["source_ref"] or "")
                    or r["fetched_at"] is None
                    or "synthetic" not in (r["license_note"] or "").lower()
                    or ("ingestion_run_id" in r and r["ingestion_run_id"] is None)
                ):
                    bad += 1
            check.expect(
                bad == 0, f"{info.name}: source {expected}, {bad} rows with missing provenance"
            )
        else:
            fk, parent = info.parent or ("", "")
            parents = {r["id"] for r in world.data[parent] if r["is_synthetic"]}
            orphans = sum(1 for r in rows if r[fk] not in parents)
            check.expect(
                orphans == 0,
                f"{info.name}: every row belongs to a synthetic {parent} ({orphans} do not)",
            )
            method = "extracted_by" if info.name == "consultation_insight" else "method"
            not_generated = sum(1 for r in rows if r[method] != ExtractionMethod.GENERATED.value)
            check.expect(
                not_generated == 0,
                f"{info.name}: all rows are generator ground truth ({method} = GENERATED)",
            )
    check.expect(len(seeds) == 1, f"one seed across the dataset: {sorted(seeds)}")
    check.metric("seed", int(next(iter(seeds))) if len(seeds) == 1 else sorted(seeds))
    return check.result


def check_honesty(world: World, config: ProductConfig, spec: WorldSpec) -> CheckResult:
    check = _Check("DATA-3", "No invented official codes, no real names, simulated events labelled")
    data = world.data
    for table in ("job_role", "course", "institute"):
        coded = sum(
            1 for r in data[table] if r["official_code"] is not None or r["official_code_verified"]
        )
        check.expect(coded == 0, f"{table}: no official codes set ({coded} rows have one)")
    check.expect(
        all(r["nsqf_level"] is None for r in data["job_role"] + data["course"]),
        "no NSQF levels invented",
    )
    check.expect(
        all(r["qualification_pack_id"] is None for r in data["course"]),
        "no courses linked to real QPs",
    )
    check.expect(
        all("not official" in (r["syllabus_version"] or "") for r in data["course"]),
        "every demo syllabus is labelled 'not official'",
    )
    for table, column in (
        ("institute", "name"),
        ("employer", "name"),
        ("job_posting", "employer_name_raw"),
    ):
        real_looking = sorted(
            {r[column] for r in data[table] if not (r[column] or "").startswith("Example ")}
        )
        check.expect(
            not real_looking,
            f"{table}.{column}: all fictional 'Example ...' names {real_looking[:3]}",
        )
    events = data["sector_event"]
    check.expect(
        all(
            r["is_simulated"] and r["citation_url"] is None and "(synthetic)" in r["title"]
            for r in events
        ),
        f"{len(events)} sector events: simulated, no citation, titled '(synthetic)'",
    )
    check.expect(
        all(
            "(synthetic)" in r["title"] and "SYNTHETIC" in r["notes"] for r in data["consultation"]
        ),
        "consultations are labelled synthetic role-plays",
    )
    check.expect(
        all(r["cost_is_estimate"] for r in data["equipment"]),
        "equipment costs are marked estimates",
    )
    return check.result


def check_volumes(world: World, config: ProductConfig, spec: WorldSpec) -> CheckResult:
    check = _Check("DATA-4", "Volumes meet config/synthetic.yaml targets")
    volumes = config.synthetic.volumes
    data = world.data
    for table, target in (
        ("job_posting", volumes.job_postings),
        ("employer_survey_response", volumes.employer_survey_responses),
        ("candidate", volumes.candidates),
        ("institute", volumes.institutes),
    ):
        check.expect(
            len(data[table]) >= target, f"{table}: {len(data[table])} rows (target >= {target})"
        )
        check.metric(table, len(data[table]))
    trainers = Counter(world.institute_code[r["institute_id"]] for r in data["trainer"])
    limits = volumes.trainers_per_institute
    check.expect(
        all(limits.min <= trainers[code] <= limits.max for code in world.institute_code.values()),
        f"trainers per institute within {limits.min}-{limits.max}: "
        f"{dict(sorted(trainers.items()))}",
    )
    employers = Counter(world.district_code[r["district_id"]] for r in data["employer"])
    golden = config.scope.golden_path_district
    for district in config.scope.district_codes:
        target = (
            volumes.employers_per_district.golden_path_district
            if district == golden
            else volumes.employers_per_district.other_districts
        )
        check.expect(
            employers[district] >= target,
            f"employers in {district}: {employers[district]} (target >= {target})",
        )
    per_quarter = Counter(r["quarter"] for r in data["job_posting"])
    check.expect(
        all(per_quarter[q] > 0 for q in world.quarters),
        f"postings in every history quarter: {[per_quarter[q] for q in world.quarters]}",
    )
    return check.result


def check_plausibility(world: World, config: ProductConfig, spec: WorldSpec) -> CheckResult:
    check = _Check("DATA-5", "Values are plausible and consistent (no absurd numbers)")
    data, as_of = world.data, spec.as_of
    first_day = quarter_start(world.quarters[0])
    salary = spec.sanity.monthly_salary_inr
    wages = [r["salary_min"] for r in data["job_posting"] if r["salary_min"] is not None]
    wages += [r["salary_max"] for r in data["job_posting"] if r["salary_max"] is not None]
    wages += [
        r["salary_monthly_inr"]
        for r in data["placement_outcome"]
        if r["salary_monthly_inr"] is not None
    ]
    check.expect(
        bool(wages) and all(salary.min <= w <= salary.max for w in wages),
        f"{len(wages)} monthly salaries within Rs {salary.min}-{salary.max} "
        f"(min {min(wages, default=0)}, max {max(wages, default=0)})",
    )
    check.expect(
        all(
            r["salary_min"] is None or r["salary_min"] <= r["salary_max"]
            for r in data["job_posting"]
        ),
        "salary_min <= salary_max on every posting",
    )
    postings = data["job_posting"]
    check.expect(
        all(
            r["quarter"] == quarter_of(r["posted_on"]) and first_day <= r["posted_on"] <= as_of
            for r in postings
        ),
        f"posting dates inside {world.quarters[0]}..{as_of} and matching their quarter",
    )
    check.expect(
        len({r["dedupe_key"] for r in postings}) == len(postings),
        "no duplicate postings (dedupe keys unique)",
    )
    roles_per_posting = Counter(r["posting_id"] for r in data["posting_role"])
    skills_per_posting = Counter(r["posting_id"] for r in data["posting_skill"])
    check.expect(
        all(roles_per_posting[r["id"]] == 1 and skills_per_posting[r["id"]] >= 1 for r in postings),
        "every posting has exactly one role and at least one skill",
    )
    submitted = [r["submitted_at"].astimezone(IST).date() for r in data["employer_survey_response"]]
    check.expect(
        all(first_day <= d <= as_of for d in submitted), "survey answers dated inside the history"
    )
    seats = spec.sanity.seats_per_offering
    completed = Counter(
        r["course_offering_id"]
        for r in data["enrollment"]
        if r["status"] == EnrollmentStatus.COMPLETED.value
    )
    enrolled = Counter(r["course_offering_id"] for r in data["enrollment"])
    offerings = data["course_offering"]
    check.expect(
        all(
            seats.min <= r["seats"] <= seats.max and r["seats_filled"] <= r["seats"]
            for r in offerings
        ),
        f"seats within {seats.min}-{seats.max} and seats_filled <= seats",
    )
    check.expect(
        all(
            enrolled[r["id"]] == r["seats_filled"]
            and abs(r["seats_filled"] * r["completion_rate"] - completed[r["id"]]) < 0.01
            for r in offerings
        ),
        "enrollments match seats_filled, and completers match completion_rate",
    )
    status = {r["id"]: r for r in data["enrollment"]}
    outcomes = data["placement_outcome"]
    check.expect(
        len(outcomes) == sum(completed.values())
        and all(
            status[r["enrollment_id"]]["status"] == EnrollmentStatus.COMPLETED.value
            for r in outcomes
        ),
        f"one placement outcome per completer ({len(outcomes)})",
    )
    check.expect(
        all(
            not r["placed"]
            or (status[r["enrollment_id"]]["completed_on"] <= r["placed_on"] <= as_of)
            for r in outcomes
        ),
        "placements dated after course completion and before the data cut-off",
    )
    check.expect(
        all(r["enrolled_on"] <= r["completed_on"] for r in data["enrollment"] if r["completed_on"]),
        "completion dates after enrollment dates",
    )
    check.expect(
        all(1 <= r["rating"] <= 5 and r["rated_on"] <= as_of for r in data["employer_rating"]),
        f"{len(data['employer_rating'])} employer ratings between 1 and 5",
    )
    _employer_realism(check, world, spec)
    rates = [r["completion_rate"] for r in offerings]
    check.metric("completion_rate_range", [min(rates), max(rates)])
    return check.result


def _employer_realism(check: _Check, world: World, spec: WorldSpec) -> None:
    """A demo employer's ads, hires and apprentices must fit what its own survey says."""
    data = world.data
    employer_code = {r["id"]: r["code"] for r in data["employer"]}
    # Survey answers: (employer, quarter) -> {role: headcount}; willingness per employer.
    asked: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    unwilling: set[str] = set()
    for r in data["employer_survey_response"]:
        code = employer_code.get(r["employer_id"])
        if code is None:
            continue
        for need in r["roles_json"]:
            role = world.role_code.get(uuid.UUID(need["role_id"]))
            asked[(code, world.survey_quarter(r))][role] = need["count"]
        if r["apprenticeship_willingness"] == "NO" or not r["apprentices_possible"]:
            unwilling.add(code)
    role_of = {r["posting_id"]: world.role_code[r["role_id"]] for r in data["posting_role"]}
    ads: Counter[tuple[str, str, str]] = Counter()
    for r in data["job_posting"]:
        if (code := employer_code.get(r["employer_id"])) is not None:
            ads[(code, r["quarter"], role_of[r["id"]])] += 1
    slack = spec.postings.directory_ads_slack
    too_many = sorted(
        f"{code} {quarter} {role}: {n} ads"
        for (code, quarter, role), n in ads.items()
        if n > math.ceil(asked[(code, quarter)].get(role, 0) / 4) + slack
    )
    check.expect(
        not too_many,
        f"demo employers post no more ads than their survey headcount suggests {too_many[:3]}",
    )
    apprentices = sorted(
        {
            employer_code[r["employer_id"]]
            for r in data["placement_outcome"]
            if r["placement_type"] == "APPRENTICESHIP" and r["employer_id"] in employer_code
        }
        & unwilling
    )
    check.expect(
        not apprentices,
        f"no apprentices at employers that take none {apprentices}",
    )


# --------------------------------------------------------------------------- patterns
def check_pp1(world: World, config: ProductConfig, spec: WorldSpec) -> CheckResult:
    pattern = config.synthetic.planted_patterns["PP1"]
    check = _Check(
        "PP1",
        "EV demand and EV skills grow in Nashik and Pune; Nashik training does not supply them",
    )
    targets = spec.pattern_targets
    for district in pattern.districts:
        ev = world.sector_postings("EV", district)
        check.expect(
            strictly_increasing(ev), f"{district} EV-role postings rise every quarter: {ev}"
        )
        check.metric(f"{district}.ev_postings", ev)
        mentions = world.skill_mentions(district)
        for skill in targets.ev_skills:
            series = mentions.get(skill, [0] * len(world.quarters))
            trend = world.trend(series)
            check.expect(
                strictly_increasing(series),
                f"{district} {skill} mentions rise every quarter: {series}",
            )
            check.expect(
                trend.status == TrendStatus.EMERGING, f"{district} {skill} is {trend.describe()}"
            )
            check.metric(f"{district}.{skill}", series)
        if "SOLAR_PV" in pattern.sectors:
            for skill in targets.solar_skills:
                trend = world.trend(mentions.get(skill, [0] * len(world.quarters)))
                check.expect(
                    trend.status == TrendStatus.EMERGING,
                    f"{district} {skill} is {trend.describe()}",
                )

    # "Existing traditional electrical course coverage remains relatively low" (golden path).
    golden = config.scope.golden_path_district
    teaching = sorted(
        {
            world.course_code[r["course_id"]]
            for r in world.data["course_offering"]
            if world.institute_district[world.institute_code[r["institute_id"]]] == golden
            and set(world.taught.get(world.course_code[r["course_id"]], {}))
            & set(targets.ev_skills)
        }
    )
    check.expect(
        not teaching, f"no course offered in {golden} teaches an EV skill in any year {teaching}"
    )
    for role in sorted(r for r, s in world.role_sector.items() if s == "EV"):
        for rule in ("primary", "any"):
            ratio, status = world.mismatch(role, golden, rule)
            check.expect(
                status == MismatchStatus.UNDERSUPPLIED,
                f"{golden} {role} supply/openings = {_pct(ratio)} ({rule} mapping) "
                f"-> {status.value}",
            )
    return check.result


def check_pp2(world: World, config: ProductConfig, spec: WorldSpec) -> CheckResult:
    target = spec.pattern_targets.golden_course
    check = _Check("PP2", f"{target.course} at {target.institute} has poor EV skill coverage")
    flags = config.scoring.course_health.flags
    district = world.institute_district.get(target.institute)
    check.expect(
        district in config.synthetic.planted_patterns["PP2"].districts,
        f"{target.institute} is in {district}",
    )
    offered = any(
        world.institute_code[r["institute_id"]] == target.institute
        and world.course_code[r["course_id"]] == target.course
        and r["academic_year"] == world.latest_academic_year()
        for r in world.data["course_offering"]
    )
    check.expect(
        offered, f"{target.institute} runs {target.course} in {world.latest_academic_year()}"
    )
    modules = world.course_modules.get(target.course, [])
    check.expect(modules == target.modules, f"modules: {modules}")
    taught = world.taught.get(target.course, {})
    for skill in spec.pattern_targets.ev_skills:
        check.expect(
            taught.get(skill, 0) == 0, f"{skill} is not taught (coverage 0 -> ADD_MODULE candidate)"
        )

    emerging = world.emerging_skills(district)
    roles = world.course_roles.get(target.course, {})
    check.expect(target.ev_role in roles, f"{target.course} is mapped to {target.ev_role}")
    for role in sorted(roles):
        boosted = world.coverage(target.course, role, emerging)
        plain = world.coverage(target.course, role, set())
        check.note(f"coverage for {role}: {boosted:.2f} (plain {plain:.2f})")
        check.metric(f"coverage.{role}", round(boosted, 4))
    # docs/03-prd.md §7.7: a course's coverage is measured over the union of the skills of
    # every role it maps to (each skill at its highest importance).
    course_coverage = world.course_coverage(target.course, emerging)
    course_plain = world.course_coverage(target.course, set())
    boosted = world.coverage(target.course, target.ev_role, emerging)
    limit = flags.outdated_coverage_below
    check.expect(
        course_coverage < limit and course_plain < limit,
        f"course coverage over all mapped roles {course_coverage:.2f} (plain {course_plain:.2f}) "
        f"< {limit} -> OUTDATED",
    )
    check.expect(boosted < limit, f"{target.ev_role} coverage {boosted:.2f} < {limit}")
    check.metric("course_coverage", round(course_coverage, 4))
    # ADD_MODULE rule (docs/03-prd.md §7.8): important for a mapped role, EMERGING, untaught.
    min_importance = config.scoring.recommendations.add_module.min_skill_importance
    for skill in spec.pattern_targets.ev_skills:
        importance = max((world.role_skills[r].get(skill, (0.0, 0))[0] for r in roles), default=0.0)
        check.expect(
            importance >= min_importance and skill in emerging and taught.get(skill, 0) == 0,
            f"ADD_MODULE {skill}: importance {importance} >= {min_importance}, "
            f"EMERGING in {district}, untaught",
        )
    return check.result


def check_pp3(world: World, config: ProductConfig, spec: WorldSpec) -> CheckResult:
    target = spec.pattern_targets.oversupply
    check = _Check(
        "PP3", f"{target.role} is oversupplied in {target.district}, with weak placement"
    )
    postings = world.role_postings(target.district).get(target.role, [0] * len(world.quarters))
    check.expect(
        all(b <= a for a, b in zip(postings, postings[1:], strict=False))
        and postings[-1] < postings[0],
        f"{target.role} postings never rise and end lower: {postings}",
    )
    limits = config.scoring.mismatch
    openings = world.openings(target.role, target.district)
    for rule in ("primary", "any"):
        ratio, status = world.mismatch(target.role, target.district, rule)
        check.expect(
            status == MismatchStatus.OVERSUPPLIED,
            f"supply {world.supply(target.role, target.district, rule):.1f} / openings "
            f"{openings:.1f} = {_pct(ratio)} > {limits.oversupplied_above} ({rule} mapping) "
            f"-> {status.value}",
        )
    years = sorted({r["academic_year"] for r in world.data["course_offering"]})
    for year in years:
        supplied = _supply_in_year(world, target.role, target.district, year)
        check.expect(
            supplied > openings * limits.oversupplied_above,
            f"{year}: trained output {supplied:.1f} stays above "
            f"{limits.oversupplied_above} x openings",
        )
    low = config.scoring.course_health.flags.low_placement_rate_below
    pairs = {
        pair: value
        for pair, value in world.placement_rates().items()
        if world.institute_district[pair[0]] == target.district
        and world.course_roles.get(pair[1], {}).get(target.role) is True
    }
    check.expect(bool(pairs), f"{target.district} has {target.role} courses")
    for (institute, course), (completed, placed) in pairs.items():
        rate = placed / completed if completed else 0.0
        check.expect(
            rate < low,
            f"{institute} {course}: placed {placed}/{completed} = {rate:.2f} < {low} "
            "-> LOW_PLACEMENT",
        )
    placed_in_role, completers = world.absorption().get((target.role, target.district), (0, 0))
    check.note(f"absorption into {target.role}: {placed_in_role}/{completers}")
    check.metric("postings", postings)
    check.metric("ratio", round(world.mismatch(target.role, target.district)[0] or 0.0, 4))
    return check.result


def _supply_in_year(world: World, role: str, district: str, year: str) -> float:
    default_rate = world.scoring.supply.default_completion_rate
    total = 0.0
    for r in world.data["course_offering"]:
        if r["academic_year"] != year:
            continue
        if world.institute_district[world.institute_code[r["institute_id"]]] != district:
            continue
        if world.course_roles.get(world.course_code[r["course_id"]], {}).get(role) is not True:
            continue
        rate = r["completion_rate"] if r["completion_rate"] is not None else default_rate
        total += r["seats_filled"] * rate
    return total


def check_pp4(world: World, config: ProductConfig, spec: WorldSpec) -> CheckResult:
    target = spec.pattern_targets.declining
    check = _Check("PP4", f"{target.skill} demand declines over the last four quarters")
    window = config.scoring.trend.window_quarters
    statewide = world.skill_mentions().get(target.skill, [0] * len(world.quarters))
    trend = world.trend(statewide)
    check.expect(
        strictly_decreasing(statewide[-window:]),
        f"statewide mentions Q1>Q2>Q3>Q4: {statewide[-window:]}",
    )
    check.expect(trend.status == TrendStatus.DECLINING, f"statewide {trend.describe()}")
    check.metric("statewide", statewide)
    for district in config.synthetic.planted_patterns["PP4"].districts:
        series = world.skill_mentions(district).get(target.skill, [0] * len(world.quarters))
        district_trend = world.trend(series)
        check.expect(
            strictly_decreasing(series[-window:])
            and district_trend.status == TrendStatus.DECLINING,
            f"{district} {district_trend.describe()}",
        )
    role_series = [
        sum(v)
        for v in zip(
            *[
                world.role_postings(d).get(target.role, [0] * len(world.quarters))
                for d in config.scope.district_codes
            ],
            strict=True,
        )
    ]
    check.expect(
        strictly_decreasing(role_series[-window:]),
        f"{target.role} postings Q1>Q2>Q3>Q4: {role_series[-window:]}",
    )

    # DEMOTE_MODULE candidate (docs/03-prd.md §7.8) in the golden-path course.
    course = spec.pattern_targets.golden_course
    district = world.institute_district.get(course.institute)
    declining = {
        s for s, t in world.skill_trends(district).items() if t.status == TrendStatus.DECLINING
    }
    share_needed = config.scoring.recommendations.demote_module.min_declining_weight_share
    module_bands: dict[str, dict[str, int]] = defaultdict(dict)
    titles = {
        r["id"]: r["title"]
        for r in world.data["course_module"]
        if world.course_code[r["course_id"]] == course.course
    }
    for r in world.data["module_skill"]:
        if r["module_id"] in titles:
            module_bands[titles[r["module_id"]]][world.skill_code[r["skill_id"]]] = r["band_taught"]
    candidates = []
    for title, bands in module_bands.items():
        share = sum(b for s, b in bands.items() if s in declining) / sum(bands.values())
        if share >= share_needed:
            candidates.append(title)
    check.expect(
        any(target.skill in module_bands[t] for t in candidates),
        f"DEMOTE_MODULE candidates in {course.course}: {candidates} "
        f"(>= {share_needed:.0%} declining)",
    )
    return check.result


def check_pp5(world: World, config: ProductConfig, spec: WorldSpec) -> CheckResult:
    pattern = config.synthetic.planted_patterns["PP5"]
    check = _Check("PP5", "The Nashik EV event lifts future EV demand")
    event_id = synthetic_id("sector_event", spec.pattern_targets.event)
    event = next((r for r in world.data["sector_event"] if r["id"] == event_id), None)
    if not check.expect(
        event is not None, f"event '{spec.pattern_targets.event}' is in the dataset"
    ):
        return check.result
    district, sector = (
        world.district_code[event["district_id"]],
        world.sector_code[event["sector_id"]],
    )
    check.expect(
        district in pattern.districts and sector in pattern.sectors,
        f"event is in {district}, sector {sector}",
    )
    check.expect(
        event["is_synthetic"] and event["is_simulated"], "event is synthetic and simulated"
    )
    impact = config.scoring.event_impact
    uplift = world.event_uplift(event)
    factor = (
        event["realization_factor"]
        if event["realization_factor"] is not None
        else impact.default_realization_factor
    )
    expected = event["expected_jobs"] * factor
    total = sum(sum(roles.values()) for roles in uplift.values())
    check.expect(
        abs(total - expected) < 1e-6,
        f"uplift {total:.0f} jobs = {event['expected_jobs']} x {factor}",
    )
    event_roles = sorted({role for roles in uplift.values() for role in roles})
    check.expect(
        bool(uplift) and all(value > 0 for roles in uplift.values() for value in roles.values()),
        f"announced {event['announced_quarter']}; jobs added in {sorted(uplift)} "
        f"(+{impact.lag_start_quarter}..+{impact.lag_end_quarter} quarters) across {event_roles}",
    )
    horizon = world.forecast_quarters()
    outside = sorted(set(uplift) - set(horizon))
    check.expect(
        bool(uplift) and not outside,
        f"every lag quarter is inside the forecast horizon {horizon[0]}..{horizon[-1]}"
        + (f" (outside: {outside})" if outside else ""),
    )
    coverage_factor = config.scoring.demand.openings.coverage_factors.formal_heavy
    baseline = [
        v / coverage_factor for v in world.linear_forecast(world.sector_postings(sector, district))
    ]
    lifted = [b + sum(uplift.get(q, {}).values()) for b, q in zip(baseline, horizon, strict=True)]
    check.note(
        f"{district} {sector} quarterly openings (postings / coverage factor) forecast for "
        f"{horizon[0]}: straight line {baseline[0]:.0f}, with the event {lifted[0]:.0f}"
    )
    check.metric(
        "uplift_by_quarter", {q: round(sum(r.values()), 1) for q, r in sorted(uplift.items())}
    )
    check.metric(
        "forecast",
        {
            q: [round(b, 1), round(up, 1)]
            for q, b, up in zip(horizon, baseline, lifted, strict=True)
        },
    )
    return check.result


def check_pp6(world: World, config: ProductConfig, spec: WorldSpec) -> CheckResult:
    check = _Check("PP6", "Institutes that teach EV skills place better; absorption is computable")
    ev_skills = set(spec.pattern_targets.ev_skills)
    rates = world.placement_rates()
    ev_pairs = {p: v for p, v in rates.items() if set(world.taught.get(p[1], {})) & ev_skills}
    other_pairs = {p: v for p, v in rates.items() if p not in ev_pairs}

    def pooled(pairs: dict) -> float:
        completed = sum(c for c, _ in pairs.values())
        return sum(p for _, p in pairs.values()) / completed if completed else 0.0

    ev_rate, other_rate = pooled(ev_pairs), pooled(other_pairs)
    check.expect(
        bool(ev_pairs) and ev_rate > other_rate,
        f"placement: EV-teaching courses {ev_rate:.2f} vs others {other_rate:.2f}",
    )
    for (institute, course), (completed, placed) in sorted(ev_pairs.items()):
        rate = placed / completed if completed else 0.0
        check.expect(rate > other_rate, f"{institute} {course}: {placed}/{completed} = {rate:.2f}")
    by_institute: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for (institute, _), (completed, placed) in rates.items():
        by_institute[institute][0] += completed
        by_institute[institute][1] += placed
    institute_rates = {i: p / c for i, (c, p) in by_institute.items() if c}
    best = max(institute_rates, key=lambda i: institute_rates[i])
    check.expect(
        best == spec.pattern_targets.ev_training_institute,
        f"best-placing institute: {best} ({institute_rates[best]:.2f})",
    )
    absorption = world.absorption()
    districts = {d for _, d in absorption}
    check.expect(
        bool(absorption)
        and all(
            0 <= placed <= completers and completers > 0
            for placed, completers in absorption.values()
        ),
        f"absorption computable for {len(absorption)} role x district pairs in "
        f"{len(districts)} districts",
    )
    for (role, district), (placed, completers) in absorption.items():
        check.note(
            f"absorption {role} in {district}: {placed}/{completers} = {placed / completers:.2f}"
        )
    retention_known = [
        r["retained_6m"] for r in world.data["placement_outcome"] if r["retained_6m"] is not None
    ]
    check.expect(
        bool(retention_known), f"6-month retention known for {len(retention_known)} placements"
    )
    check.metric(
        "institute_placement_rates", {i: round(r, 3) for i, r in sorted(institute_rates.items())}
    )
    check.metric(
        "absorption", {f"{r}|{d}": round(p / c, 3) for (r, d), (p, c) in absorption.items()}
    )
    return check.result


def check_pp7(world: World, config: ProductConfig, spec: WorldSpec) -> CheckResult:
    pattern = config.synthetic.planted_patterns["PP7"]
    check = _Check("PP7", "Employer surveys in Nashik and Pune ask for more EV skills over time")
    ev_skills = set(spec.pattern_targets.ev_skills)
    for sector in pattern.sectors:
        for district in pattern.districts:
            headcount = world.survey_headcount(sector, district)
            check.expect(
                strictly_increasing(headcount),
                f"{district} {sector} headcount asked for, per quarter: {headcount}",
            )
            share = world.survey_skill_share(ev_skills, district)
            check.expect(
                share[-1] > share[0],
                f"{district} answers naming EV skills: {share[0]:.0%} -> {share[-1]:.0%}",
            )
            check.metric(f"{district}.{sector}.headcount", headcount)
    return check.result


def check_controls(world: World, config: ProductConfig, spec: WorldSpec) -> CheckResult:
    check = _Check("CTRL-1", "No unplanned trend muddles the story")
    declining_target = spec.pattern_targets.declining.skill
    for district in [None, *config.scope.district_codes]:
        declining = sorted(
            s for s, t in world.skill_trends(district).items() if t.status == TrendStatus.DECLINING
        )
        check.expect(
            set(declining) <= {declining_target},
            f"{district or 'statewide'}: DECLINING skills {declining}",
        )
    course = spec.pattern_targets.golden_course
    district = world.institute_district.get(course.institute)
    primary = next((r for r, p in world.course_roles.get(course.course, {}).items() if p), None)
    taught = world.taught.get(course.course, {})
    fully = sorted(
        s
        for s, (_, band) in world.role_skills.get(primary or "", {}).items()
        if taught.get(s, 0) >= band
    )
    emerging = world.emerging_skills(district)
    check.expect(
        not set(fully) & emerging,
        f"skills {course.course} already teaches well {fully} are not EMERGING in {district}",
    )
    check.note(f"EMERGING in {district}: {sorted(emerging)}")
    return check.result


CHECKS: list[tuple[str | None, Callable[[World, ProductConfig, WorldSpec], CheckResult]]] = [
    (None, check_marking),
    (None, check_provenance),
    (None, check_honesty),
    (None, check_volumes),
    (None, check_plausibility),
    ("PP1", check_pp1),
    ("PP2", check_pp2),
    ("PP3", check_pp3),
    ("PP4", check_pp4),
    ("PP5", check_pp5),
    ("PP6", check_pp6),
    ("PP7", check_pp7),
    (None, check_controls),
]


def run_checks(dataset: Dataset, config: ProductConfig, spec: WorldSpec) -> list[CheckResult]:
    world = World(dataset, config)
    results = []
    for pattern_id, check in CHECKS:
        pattern = config.synthetic.planted_patterns.get(pattern_id) if pattern_id else None
        if pattern_id and (pattern is None or not pattern.enabled):
            results.append(CheckResult(pattern_id, f"{pattern_id} switched off in config", None))
            continue
        try:
            results.append(check(world, config, spec))
        except (KeyError, ValueError, ZeroDivisionError, StopIteration) as exc:
            name = pattern_id or check.__name__
            results.append(
                CheckResult(name, f"{name} could not be computed", False, [f"[FAIL] {exc!r}"])
            )
    return results


def dataset_summary(
    dataset: Dataset, config: ProductConfig, results: list[CheckResult]
) -> dict[str, Any]:
    """A compact, deterministic description of the dataset (written to summary.json)."""
    world = World(dataset, config)
    return {
        "is_synthetic": True,
        "rows": {t.name: len(dataset[t.name]) for t in SYNTHETIC_TABLES},
        "quarters": world.quarters,
        "postings_by_district": {
            d: [sum(v) for v in zip(*world.role_postings(d).values(), strict=True)]
            for d in config.scope.district_codes
        },
        "checks": [r.to_dict() for r in results],
        "all_passed": all(r.passed is not False for r in results),
    }
