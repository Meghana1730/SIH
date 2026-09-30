"""Reference calculations over a dataset, following docs/03-prd.md §7 and config/scoring.yaml.

The validator uses them to prove that the planted patterns are really in the data (the
same numbers the analytics engines will compute later). They work on any Dataset: freshly
generated, read from the CSV export, or read back from the database.

Definitions (all thresholds come from config/scoring.yaml):
* postings(role, district, quarter): job postings classified as the role (posting_role).
* mentions(skill, district, quarter): postings naming the skill (posting_skill).
* trend over the last `trend.window_quarters`: EMERGING if the second half of the window
  grew by >= min_relative_growth over the first half AND the second half has
  >= min_mentions; DECLINING if the last `consecutive_quarter_drops` quarters each fell and
  the fall over that run is >= min_relative_decline; otherwise STABLE.
* openings(role, district) = postings in the last `openings.window_quarters` quarters /
  the role's coverage factor (formal-heavy by default).
* supply(role, district) = sum over the latest academic year's offerings in the district
  mapped to the role of seats_filled x completion_rate (default_completion_rate if
  unknown). "primary" counts a course only for its primary role; "any" also for its
  secondary roles.
* coverage(course, role) = sum(importance x covered) / sum(importance); covered = 1 at or
  above the required band, partial_credit below it, 0 if not taught; importance x
  emerging_skill_importance_multiplier for skills EMERGING in the district. The course's
  own coverage uses the union of all its mapped roles' skills (highest importance each).
* placement rate = placed / completed over the last `placement_lookback_cohorts` cohorts.
* absorption(role, district) = completers placed in that role / completers of courses whose
  primary role it is.
* event uplift: expected_jobs x realization_factor, spread evenly over quarters
  +lag_start..+lag_end after the announcement, split across the sector's roles.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta, timezone
from typing import Any

from app.config import ProductConfig
from app.models.enums import EnrollmentStatus, MismatchStatus, TrendStatus
from app.synthetic.generator import Dataset
from app.synthetic.timeline import quarter_of, quarter_range, shift_quarter

IST = timezone(timedelta(hours=5, minutes=30))
QUARTERS_PER_YEAR = 4


@dataclass(frozen=True)
class Trend:
    status: TrendStatus
    window: list[int]
    growth: float | None  # second half vs first half of the window
    recent_mentions: int
    drops: int  # consecutive quarter-on-quarter falls at the end of the window
    decline: float | None  # fall over those consecutive drops

    def describe(self) -> str:
        growth = "n/a" if self.growth is None else f"{self.growth:+.0%}"
        decline = "n/a" if self.decline is None else f"{self.decline:.0%}"
        return (
            f"{self.status.value}: window {self.window}, growth {growth}, recent mentions "
            f"{self.recent_mentions}, consecutive drops {self.drops}, decline {decline}"
        )


class World:
    """Indexes a dataset for the calculations above."""

    def __init__(self, dataset: Dataset, config: ProductConfig) -> None:
        self.data = dataset
        self.config = config
        self.scoring = config.scoring
        history = config.synthetic.history
        self.quarters = quarter_range(history.start_quarter, history.end_quarter)
        self.end_quarter = history.end_quarter

        self.district_code = {r["id"]: r["code"] for r in dataset["district"]}
        self.district_id = {code: id_ for id_, code in self.district_code.items()}
        self.sector_code = {r["id"]: r["code"] for r in dataset["sector"]}
        self.skill_code = {r["id"]: r["code"] for r in dataset["skill"]}
        self.role_code = {r["id"]: r["code"] for r in dataset["job_role"]}
        self.role_sector = {
            r["code"]: self.sector_code.get(r["sector_id"]) for r in dataset["job_role"]
        }
        self.course_code = {r["id"]: r["code"] for r in dataset["course"]}
        self.institute_code = {r["id"]: r["code"] for r in dataset["institute"]}
        self.institute_district = {
            r["code"]: self.district_code.get(r["district_id"]) for r in dataset["institute"]
        }
        self.offerings = {r["id"]: r for r in dataset["course_offering"]}

        # posting id -> (district code, quarter)
        self.posting_place = {
            r["id"]: (self.district_code.get(r["district_id"]), r["quarter"])
            for r in dataset["job_posting"]
        }
        # course code -> {role code: is_primary}
        self.course_roles: dict[str, dict[str, bool]] = defaultdict(dict)
        for r in dataset["course_role"]:
            self.course_roles[self.course_code[r["course_id"]]][self.role_code[r["role_id"]]] = r[
                "is_primary"
            ]
        # course code -> {skill code: highest band taught}
        module_course = {
            r["id"]: self.course_code[r["course_id"]] for r in dataset["course_module"]
        }
        self.course_modules: dict[str, list[str]] = defaultdict(list)
        for r in sorted(dataset["course_module"], key=lambda r: r["sequence"]):
            self.course_modules[module_course[r["id"]]].append(r["title"])
        self.taught: dict[str, dict[str, int]] = defaultdict(dict)
        for r in dataset["module_skill"]:
            course, skill = module_course[r["module_id"]], self.skill_code[r["skill_id"]]
            self.taught[course][skill] = max(r["band_taught"], self.taught[course].get(skill, 0))
        # role code -> {skill code: (importance, required band)}
        self.role_skills: dict[str, dict[str, tuple[float, int]]] = defaultdict(dict)
        for r in dataset["role_skill"]:
            self.role_skills[self.role_code[r["role_id"]]][self.skill_code[r["skill_id"]]] = (
                r["importance"],
                r["required_band"],
            )

    # ------------------------------------------------------------------ demand
    def _series(self, counts: dict[str, list[int]], key: str) -> list[int]:
        return counts.get(key, [0] * len(self.quarters))

    def _count(
        self, rows: Iterable[dict[str, Any]], key_column: str, codes: dict, district: str | None
    ) -> dict[str, list[int]]:
        index = {q: i for i, q in enumerate(self.quarters)}
        counts: dict[str, list[int]] = defaultdict(lambda: [0] * len(self.quarters))
        for r in rows:
            place = self.posting_place.get(r["posting_id"])
            if place is None or place[1] not in index:
                continue
            if district is not None and place[0] != district:
                continue
            counts[codes[r[key_column]]][index[place[1]]] += 1
        return counts

    def role_postings(self, district: str | None = None) -> dict[str, list[int]]:
        """role code -> postings per history quarter (district=None: all districts)."""
        return self._count(self.data["posting_role"], "role_id", self.role_code, district)

    def skill_mentions(self, district: str | None = None) -> dict[str, list[int]]:
        """skill code -> postings naming the skill, per history quarter."""
        return self._count(self.data["posting_skill"], "skill_id", self.skill_code, district)

    def sector_postings(self, sector: str, district: str | None = None) -> list[int]:
        totals = [0] * len(self.quarters)
        for role, counts in self.role_postings(district).items():
            if self.role_sector.get(role) == sector:
                totals = [a + b for a, b in zip(totals, counts, strict=True)]
        return totals

    def trend(self, series: list[int]) -> Trend:
        rules = self.scoring.trend
        window = series[-rules.window_quarters :]
        half = len(window) // 2
        earlier, recent = sum(window[:half]), sum(window[-half:])
        growth = None if earlier == 0 else (recent - earlier) / earlier
        drops = 0
        for i in range(len(window) - 1, 0, -1):
            if window[i] < window[i - 1]:
                drops += 1
            else:
                break
        run_start = window[len(window) - 1 - drops]
        decline = None if drops == 0 or run_start == 0 else (run_start - window[-1]) / run_start
        emerging = recent >= rules.emerging.min_mentions and (
            growth is None
            and recent > 0
            or growth is not None
            and growth >= rules.emerging.min_relative_growth
        )
        declining = (
            drops >= rules.declining.consecutive_quarter_drops
            and decline is not None
            and decline >= rules.declining.min_relative_decline
        )
        status = (
            TrendStatus.EMERGING
            if emerging
            else TrendStatus.DECLINING if declining else TrendStatus.STABLE
        )
        return Trend(status, window, growth, recent, drops, decline)

    def skill_trends(self, district: str | None = None) -> dict[str, Trend]:
        return {
            skill: self.trend(counts)
            for skill, counts in sorted(self.skill_mentions(district).items())
        }

    def emerging_skills(self, district: str | None) -> set[str]:
        return {
            s for s, t in self.skill_trends(district).items() if t.status == TrendStatus.EMERGING
        }

    # ------------------------------------------------------------------ supply and mismatch
    def openings(self, role: str, district: str) -> float:
        settings = self.scoring.demand.openings
        window = settings.window_quarters
        recent = sum(self._series(self.role_postings(district), role)[-window:])
        return recent / settings.factor_for(role)[0]

    def latest_academic_year(self) -> str | None:
        years = [r["academic_year"] for r in self.data["course_offering"]]
        return max(years) if years else None

    def supply(self, role: str, district: str, rule: str = "primary") -> float:
        year = self.latest_academic_year()
        default_rate = self.scoring.supply.default_completion_rate
        total = 0.0
        for r in self.data["course_offering"]:
            if r["academic_year"] != year:
                continue
            if self.institute_district[self.institute_code[r["institute_id"]]] != district:
                continue
            roles = self.course_roles.get(self.course_code[r["course_id"]], {})
            if role not in roles or (rule == "primary" and not roles[role]):
                continue
            rate = r["completion_rate"] if r["completion_rate"] is not None else default_rate
            total += (r["seats_filled"] or 0) * rate
        return total

    def mismatch(
        self, role: str, district: str, rule: str = "primary"
    ) -> tuple[float | None, MismatchStatus]:
        openings = self.openings(role, district)
        if openings == 0:
            return None, MismatchStatus.INSUFFICIENT_DATA
        ratio = self.supply(role, district, rule) / openings
        limits = self.scoring.mismatch
        if ratio < limits.undersupplied_below:
            return ratio, MismatchStatus.UNDERSUPPLIED
        if ratio > limits.oversupplied_above:
            return ratio, MismatchStatus.OVERSUPPLIED
        return ratio, MismatchStatus.BALANCED

    # ------------------------------------------------------------------ courses
    def coverage(self, course: str, role: str, emerging: set[str]) -> float:
        """Coverage of one role's skills (FR-8.3 shows it per mapped role)."""
        return self._coverage(course, self.role_skills.get(role, {}), emerging)

    def course_coverage(self, course: str, emerging: set[str]) -> float:
        """The course's coverage (docs/03-prd.md §7.7): over the union of the skills of every
        role it maps to, each skill at its highest importance."""
        skills: dict[str, tuple[float, int]] = {}
        for role in self.course_roles.get(course, {}):
            for skill, (importance, band) in self.role_skills.get(role, {}).items():
                if skill not in skills or importance > skills[skill][0]:
                    skills[skill] = (importance, band)
        return self._coverage(course, skills, emerging)

    def _coverage(
        self, course: str, skills: dict[str, tuple[float, int]], emerging: set[str]
    ) -> float:
        settings = self.scoring.course_health.coverage
        taught = self.taught.get(course, {})
        numerator = denominator = 0.0
        for skill, (importance, required) in skills.items():
            weight = importance * (
                settings.emerging_skill_importance_multiplier if skill in emerging else 1.0
            )
            band = taught.get(skill, 0)
            covered = 1.0 if band >= required else settings.partial_credit if band > 0 else 0.0
            numerator += weight * covered
            denominator += weight
        return numerator / denominator if denominator else 0.0

    # ------------------------------------------------------------------ outcomes
    def _cohorts(self) -> dict[uuid.UUID, tuple[int, int]]:
        """offering id -> (completed, placed)."""
        enrollment_offering = {}
        completed: dict[Any, int] = defaultdict(int)
        for r in self.data["enrollment"]:
            enrollment_offering[r["id"]] = r["course_offering_id"]
            if r["status"] == EnrollmentStatus.COMPLETED.value:
                completed[r["course_offering_id"]] += 1
        placed: dict[Any, int] = defaultdict(int)
        for r in self.data["placement_outcome"]:
            if r["placed"]:
                placed[enrollment_offering[r["enrollment_id"]]] += 1
        return {o: (completed[o], placed[o]) for o in self.offerings}

    def placement_rates(self) -> dict[tuple[str, str], tuple[int, int]]:
        """(institute code, course code) -> (completed, placed) over the lookback cohorts."""
        lookback = self.scoring.course_health.placement_lookback_cohorts
        cohorts = self._cohorts()
        by_pair: dict[tuple[str, str], list[tuple[str, Any]]] = defaultdict(list)
        for offering_id, r in self.offerings.items():
            pair = (self.institute_code[r["institute_id"]], self.course_code[r["course_id"]])
            by_pair[pair].append((r["academic_year"], offering_id))
        result = {}
        for pair, years in sorted(by_pair.items()):
            recent = [o for _, o in sorted(years)[-lookback:]]
            result[pair] = (
                sum(cohorts[o][0] for o in recent),
                sum(cohorts[o][1] for o in recent),
            )
        return result

    def absorption(self) -> dict[tuple[str, str], tuple[int, int]]:
        """(role, district) -> (completers placed in the role, completers) for every role
        that is some course's primary role in the district."""
        enrollment_offering = {r["id"]: r["course_offering_id"] for r in self.data["enrollment"]}
        completers: dict[tuple[str, str], int] = defaultdict(int)
        in_role: dict[tuple[str, str], int] = defaultdict(int)
        primary = {
            c: next((r for r, p in roles.items() if p), None)
            for c, roles in self.course_roles.items()
        }

        def key_of(offering_id: Any) -> tuple[str, str] | None:
            r = self.offerings[offering_id]
            role = primary.get(self.course_code[r["course_id"]])
            district = self.institute_district[self.institute_code[r["institute_id"]]]
            return (role, district) if role else None

        for r in self.data["enrollment"]:
            if r["status"] == EnrollmentStatus.COMPLETED.value and (
                key := key_of(r["course_offering_id"])
            ):
                completers[key] += 1
        for r in self.data["placement_outcome"]:
            key = key_of(enrollment_offering[r["enrollment_id"]])
            if (
                key
                and r["placed"]
                and r["role_id"] is not None
                and self.role_code[r["role_id"]] == key[0]
            ):
                in_role[key] += 1
        return {key: (in_role[key], completers[key]) for key in sorted(completers)}

    # ------------------------------------------------------------------ events and forecast
    def event_uplift(self, event: dict[str, Any]) -> dict[str, dict[str, float]]:
        """quarter -> {role: extra jobs} for one sector event."""
        impact = self.scoring.event_impact
        sector = self.sector_code[event["sector_id"]]
        factor = event["realization_factor"]
        if factor is None:
            factor = impact.default_realization_factor
        jobs = (event["expected_jobs"] or 0) * factor
        lag = range(impact.lag_start_quarter, impact.lag_end_quarter + 1)
        per_quarter = jobs / len(lag)
        pattern = self.config.sectors.event_staffing.patterns.get(sector)
        if pattern:
            shares = dict(pattern)
        else:  # fallback: even_split_across_sector_roles
            roles = sorted(r for r, s in self.role_sector.items() if s == sector)
            shares = {r: 1 / len(roles) for r in roles} if roles else {}
        return {
            shift_quarter(event["announced_quarter"], step): {
                r: per_quarter * s for r, s in shares.items()
            }
            for step in lag
        }

    def forecast_quarters(self) -> list[str]:
        horizon = self.scoring.forecast.horizon_quarters
        return [shift_quarter(self.end_quarter, step) for step in range(1, horizon + 1)]

    def linear_forecast(self, series: list[int]) -> list[float]:
        """Straight-line trend over the last `history_quarters`, extended over the horizon."""
        history = [float(v) for v in series[-self.scoring.forecast.history_quarters :]]
        n = len(history)
        mean_x, mean_y = (n - 1) / 2, sum(history) / n
        spread = sum((x - mean_x) ** 2 for x in range(n))
        slope = (
            sum((x - mean_x) * (y - mean_y) for x, y in enumerate(history)) / spread
            if spread
            else 0.0
        )
        return [
            max(0.0, mean_y + slope * (n - 1 + step - mean_x))
            for step in range(1, self.scoring.forecast.horizon_quarters + 1)
        ]

    # ------------------------------------------------------------------ employer survey
    def survey_quarter(self, row: dict[str, Any]) -> str:
        return quarter_of(row["submitted_at"].astimezone(IST).date())

    def survey_headcount(self, sector: str, district: str) -> list[int]:
        """Headcount that the district's survey answers ask for, per quarter, in a sector."""
        index = {q: i for i, q in enumerate(self.quarters)}
        totals = [0] * len(self.quarters)
        for r in self.data["employer_survey_response"]:
            if self.district_code.get(r["district_id"]) != district:
                continue
            quarter = self.survey_quarter(r)
            if quarter not in index:
                continue
            for need in r["roles_json"]:
                role = self.role_code.get(uuid.UUID(need["role_id"]))
                if role and self.role_sector.get(role) == sector:
                    totals[index[quarter]] += need["count"]
        return totals

    def survey_skill_share(self, skills: set[str], district: str) -> list[float]:
        """Share of the district's survey answers per quarter that name any of the skills."""
        index = {q: i for i, q in enumerate(self.quarters)}
        answers = [0] * len(self.quarters)
        naming = [0] * len(self.quarters)
        for r in self.data["employer_survey_response"]:
            if self.district_code.get(r["district_id"]) != district:
                continue
            quarter = self.survey_quarter(r)
            if quarter not in index:
                continue
            answers[index[quarter]] += 1
            named = {self.skill_code.get(uuid.UUID(s["skill_id"])) for s in r["skills_json"]}
            if named & skills:
                naming[index[quarter]] += 1
        return [n / a if a else 0.0 for n, a in zip(naming, answers, strict=True)]
