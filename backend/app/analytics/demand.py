"""Demand index D(r, d, t), 0-100, for job roles (and skills) per district and quarter.

    D = w_P x P + w_S x S + w_G x G + w_A x A        (weights: config/scoring.yaml demand)

P  posting signal  = volume_weight x percentile(log(1 + postings in t))
                     + growth_weight x percentile(growth), growth = postings in the second half
                     of the growth window vs the first half, clipped to [growth_min, growth_max];
                     percentiles across all role x district cells of quarter t
S  survey signal   = headcount asked for in each employer's latest answer (last
                     survey_lookback_months), weighted 0.5 ^ (age in quarters / half-life),
                     scaled 0-100 across the quarter's cells
G  growth / events = jobs expected from sector events in the district and the role's sector
                     in the next lookahead_quarters (expected jobs x realisation factor,
                     spread over the configured lag window, split across the sector's roles),
                     scaled 0-100
A  absorption      = completers placed in the role / completers of courses for the role
                     (last placement_lookback_cohorts cohorts completed by t), x 100

A component without data is NOT treated as zero: it is left out, the other weights are scaled
up to add to 1 (demand.missing_components: renormalize), and confidence goes down (fewer
source types). "No data" means: no postings at all in the district (P), no survey answer in
the district in the look-back (S), no event for the role's sector in the district (G), no
completers for the role in the district (A). Zero postings for one role in a district that
has postings IS data (demand really is low).

Skills get P and S only (from posting mentions and the skills employers name), plus the
trend status (analytics/trend.py).
"""

from __future__ import annotations

import math
import uuid
from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.analytics.inputs import Inputs, RoleInfo
from app.analytics.trend import classify_trend
from app.config import ProductConfig
from app.config.base import quarter_index
from app.config.scoring import ConfidenceLevelRule
from app.models.enums import Confidence
from app.synthetic.timeline import quarter_end, shift_quarter

COMPONENTS = ("postings", "employer_survey", "growth_events", "absorption")
SOURCE_TYPES = {
    "postings": "job postings",
    "employer_survey": "employer surveys",
    "growth_events": "sector events",
    "absorption": "placement outcomes",
}


@dataclass
class Component:
    name: str
    available: bool
    value: float | None = None  # 0-100 signal
    weight: float = 0.0  # configured weight
    effective_weight: float = 0.0  # after renormalisation (0 when unavailable)
    records: int = 0
    synthetic_records: int = 0
    raw: dict[str, Any] = field(default_factory=dict)  # the observed inputs behind it
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "value": None if self.value is None else round(self.value, 2),
            "weight": self.weight,
            "effective_weight": round(self.effective_weight, 4),
            "records": self.records,
            "synthetic_records": self.synthetic_records,
            "observed": self.raw,
            **({"note": self.note} if self.note else {}),
        }


@dataclass
class DemandResult:
    level: str  # "role" | "skill"
    item_id: uuid.UUID
    district_id: uuid.UUID
    quarter: str
    score: float
    components: list[Component]
    confidence: Confidence
    trend: dict[str, Any] | None = None  # skills: trend status and window
    mention_count: int | None = None  # skills: postings naming the skill in the quarter

    @property
    def records(self) -> int:
        return sum(c.records for c in self.components if c.available)

    @property
    def synthetic_share(self) -> float:
        records = self.records
        synthetic = sum(c.synthetic_records for c in self.components if c.available)
        return round(synthetic / records, 4) if records else 0.0

    def component(self, name: str) -> Component | None:
        return next((c for c in self.components if c.name == name), None)


# --------------------------------------------------------------------------- helpers
def percentile_ranks(values: dict[Any, float]) -> dict[Any, float]:
    """Mid-rank percentile (0-1) of each value among all values (ties share a rank)."""
    ordered = sorted(values.values())
    n = len(ordered)
    return {
        key: (bisect_left(ordered, v) + 0.5 * (bisect_right(ordered, v) - bisect_left(ordered, v)))
        / n
        for key, v in values.items()
    }


def scale(values: dict[Any, float], method: str) -> dict[Any, float]:
    """0-100 across the given cells: min_max (all-equal values -> 100 if > 0 else 0) or
    percentile."""
    if not values:
        return {}
    if method == "percentile":
        return {k: 100 * v for k, v in percentile_ranks(values).items()}
    low, high = min(values.values()), max(values.values())
    if high == low:
        return {k: (100.0 if v > 0 else 0.0) for k, v in values.items()}
    return {k: 100 * (v - low) / (high - low) for k, v in values.items()}


def confidence_of(source_types: int, records: int, config: ProductConfig) -> Confidence:
    rules = config.scoring.confidence

    def meets(rule: ConfidenceLevelRule) -> bool:
        checks = (source_types >= rule.min_source_types, records >= rule.min_records)
        return all(checks) if rule.combine == "all" else any(checks)

    if meets(rules.high):
        return Confidence.HIGH
    if meets(rules.medium):
        return Confidence.MEDIUM
    return Confidence.LOW


def academic_years_completed_by(day: date, years: set[str]) -> list[str]:
    """Academic years ('2024-25') whose cohorts completed (31 July) on or before `day`."""
    return sorted(y for y in years if date(int(y[:4]) + 1, 7, 31) <= day)


# --------------------------------------------------------------------------- engine
class DemandEngine:
    def __init__(self, inputs: Inputs, config: ProductConfig) -> None:
        self.inputs = inputs
        self.config = config
        self.settings = config.scoring.demand
        self.weights = self.settings.weights.model_dump()

    # ------------------------------------------------------------------ public
    def roles(self, quarter: str) -> list[DemandResult]:
        cells = [(r, d) for r in self.inputs.roles for d in self.inputs.districts]
        posting = self._posting_signal(self.inputs.role_postings, cells, quarter)
        survey = self._survey_signal(
            cells, quarter, lambda answer, role: answer.headcount.get(role, 0)
        )
        events = self._event_signal(cells, quarter)
        absorption = self._absorption(cells, quarter)
        return [
            self._combine(
                "role", cell, quarter, [posting[cell], survey[cell], events[cell], absorption[cell]]
            )
            for cell in cells
            if any(
                c.available for c in (posting[cell], survey[cell], events[cell], absorption[cell])
            )
        ]

    def skills(self, quarter: str) -> list[DemandResult]:
        cells = [(s, d) for s in self.inputs.skills for d in self.inputs.districts]
        posting = self._posting_signal(self.inputs.skill_mentions, cells, quarter)
        survey = self._survey_signal(
            cells, quarter, lambda answer, skill: int(skill in answer.skills)
        )
        results = []
        for cell in cells:
            parts = [posting[cell], survey[cell]]
            if not any(c.available for c in parts):
                continue
            result = self._combine("skill", cell, quarter, parts)
            series = self._series(self.inputs.skill_mentions, cell, quarter)
            trend = classify_trend(series, self.config.scoring.trend)
            result.trend = {
                "status": trend.status.value,
                "window": trend.window,
                "growth": None if trend.growth is None else round(trend.growth, 4),
                "recent_mentions": trend.recent_mentions,
                "consecutive_drops": trend.drops,
                "decline": None if trend.decline is None else round(trend.decline, 4),
            }
            result.mention_count = series[-1] if series else 0
            results.append(result)
        return results

    # ------------------------------------------------------------------ components
    def _series(
        self, counts: dict, cell: tuple, quarter: str, synthetic: bool = False
    ) -> list[int]:
        """Counts per quarter from the first history quarter up to `quarter`."""
        item, district = cell
        upto = [q for q in self.inputs.quarters if quarter_index(q) <= quarter_index(quarter)]
        out = []
        for q in upto:
            c = counts.get((item, district, q))
            out.append((c.synthetic if synthetic else c.total) if c else 0)
        return out

    def _posting_signal(
        self, counts: dict, cells: list[tuple], quarter: str
    ) -> dict[tuple, Component]:
        s = self.settings.posting_signal
        window = s.growth_window_quarters
        half = window // 2
        volumes, growths, parts = {}, {}, {}
        for cell in cells:
            if cell[1] not in self.inputs.posting_districts:
                parts[cell] = Component("postings", False, note="no job postings for this district")
                continue
            series = self._series(counts, cell, quarter)
            synthetic = self._series(counts, cell, quarter, synthetic=True)
            volume = series[-1] if series else 0
            raw: dict[str, Any] = {"postings_this_quarter": volume}
            growth = None
            if len(series) >= window:
                earlier, recent = sum(series[-window:-half]), sum(series[-half:])
                if earlier:
                    growth = (recent - earlier) / earlier
                else:
                    growth = s.growth_max if recent else 0.0
                growth = min(s.growth_max, max(s.growth_min, growth))
                raw.update(
                    earlier_postings=earlier,
                    recent_postings=recent,
                    growth=round(growth, 4),
                    window_quarters=window,
                )
                growths[cell] = growth
            recent_window = series[-window:]
            volumes[cell] = math.log1p(volume)
            parts[cell] = Component(
                "postings",
                True,
                raw=raw,
                records=sum(recent_window),
                synthetic_records=sum(synthetic[-window:]),
                note=None if growth is not None else "history too short for growth: volume only",
            )
        volume_rank = percentile_ranks(volumes) if volumes else {}
        growth_rank = percentile_ranks(growths) if growths else {}
        for cell, volume_pct in volume_rank.items():
            part = parts[cell]
            if cell in growth_rank:
                part.value = 100 * (
                    s.volume_weight * volume_pct + s.growth_weight * growth_rank[cell]
                )
            else:
                part.value = 100 * volume_pct
            part.raw.update(volume_percentile=round(volume_pct, 4))
            if cell in growth_rank:
                part.raw.update(growth_percentile=round(growth_rank[cell], 4))
        return parts

    def _latest_answers(self, district: uuid.UUID, quarter: str) -> list[Any]:
        lookback = max(1, self.settings.survey_lookback_months // 3)
        now = quarter_index(quarter)
        latest: dict[Any, Any] = {}
        for answer in self.inputs.surveys:
            age = now - quarter_index(answer.quarter)
            if answer.district_id != district or not 0 <= age < lookback:
                continue
            key = answer.employer_id or answer.id
            if key not in latest or quarter_index(answer.quarter) > quarter_index(
                latest[key].quarter
            ):
                latest[key] = answer
        return list(latest.values())

    def _survey_signal(self, cells: list[tuple], quarter: str, amount) -> dict[tuple, Component]:
        half_life = self.settings.survey.half_life_quarters
        raw_values, parts = {}, {}
        answers_by_district = {d: self._latest_answers(d, quarter) for d in self.inputs.districts}
        for cell in cells:
            item, district = cell
            answers = answers_by_district[district]
            if not answers:
                parts[cell] = Component(
                    "employer_survey", False, note="no employer survey answers in the look-back"
                )
                continue
            total, asked, undecayed = 0.0, 0, 0
            for answer in answers:
                n = amount(answer, item)
                if n:
                    age = quarter_index(quarter) - quarter_index(answer.quarter)
                    total += n * 0.5 ** (age / half_life)
                    asked += 1
                    undecayed += n
            raw_values[cell] = total
            parts[cell] = Component(
                "employer_survey",
                True,
                raw={
                    "employers_answering": len(answers),
                    "employers_asking": asked,
                    "headcount": undecayed,
                    "decayed_headcount": round(total, 3),
                    "half_life_quarters": half_life,
                },
                records=len(answers),
                synthetic_records=sum(a.is_synthetic for a in answers),
            )
        for cell, value in scale(raw_values, self.settings.normalization).items():
            parts[cell].value = value
        return parts

    def event_jobs(self, role: RoleInfo, district: uuid.UUID, quarter: str) -> list[dict[str, Any]]:
        """Expected jobs for the role from events in the district, landing in the next
        lookahead quarters (events announced by `quarter`)."""
        impact = self.config.scoring.event_impact
        lookahead = self.settings.growth_events.lookahead_quarters
        now = quarter_index(quarter)
        found = []
        for event in self.inputs.events:
            if event.district_id != district or event.sector != role.sector:
                continue
            if quarter_index(event.announced_quarter) > now:
                continue
            factor = (
                event.realization_factor
                if event.realization_factor is not None
                else impact.default_realization_factor
            )
            lag = range(impact.lag_start_quarter, impact.lag_end_quarter + 1)
            per_quarter = event.expected_jobs * factor / len(lag)
            pattern = self.config.sectors.event_staffing.patterns.get(event.sector)
            if pattern:
                share = pattern.get(role.code, 0.0)
                split = "staffing pattern in config/sectors.yaml"
            else:
                sector_roles = self.inputs.sector_roles(event.sector)
                share = 1 / len(sector_roles) if sector_roles else 0.0
                split = f"even split across {len(sector_roles)} {event.sector} roles"
            landing = [
                shift_quarter(event.announced_quarter, step)
                for step in lag
                if now < quarter_index(event.announced_quarter) + step <= now + lookahead
            ]
            jobs = per_quarter * share * len(landing)
            if jobs > 0:
                found.append(
                    {
                        "event_id": str(event.id),
                        "title": event.title,
                        "announced_quarter": event.announced_quarter,
                        "expected_jobs": event.expected_jobs,
                        "realization_factor": factor,
                        "role_share": round(share, 4),
                        "split": split,
                        "quarters": landing,
                        "jobs_for_role": round(jobs, 2),
                        "is_synthetic": event.is_synthetic,
                        "is_simulated": event.is_simulated,
                    }
                )
        return found

    def _event_signal(self, cells: list[tuple], quarter: str) -> dict[tuple, Component]:
        raw_values, parts = {}, {}
        for cell in cells:
            role_id, district = cell
            events = self.event_jobs(self.inputs.roles[role_id], district, quarter)
            if not events:
                parts[cell] = Component(
                    "growth_events", False, note="no sector event for this role and district"
                )
                continue
            jobs = sum(e["jobs_for_role"] for e in events)
            raw_values[cell] = jobs
            parts[cell] = Component(
                "growth_events",
                True,
                raw={
                    "expected_jobs_next_quarters": round(jobs, 2),
                    "lookahead_quarters": self.settings.growth_events.lookahead_quarters,
                    "events": events,
                },
                records=len(events),
                synthetic_records=sum(e["is_synthetic"] for e in events),
            )
        for cell, value in scale(raw_values, self.settings.normalization).items():
            parts[cell].value = value
        return parts

    def absorption_counts(
        self, role: uuid.UUID, district: uuid.UUID, quarter: str
    ) -> tuple[int, int, int, list[str]]:
        """(completers, placed in the role, synthetic completers, academic years) for courses
        whose primary role is `role`, cohorts completed by the end of the quarter."""
        end = quarter_end(quarter)
        offerings = {
            o.id: o
            for o in self.inputs.offerings
            if o.district_id == district and o.primary_role == role
        }
        years = academic_years_completed_by(end, {o.academic_year for o in offerings.values()})
        years = years[-self.config.scoring.course_health.placement_lookback_cohorts :]
        completers = placed = synthetic = 0
        for c in self.inputs.completions:
            offering = offerings.get(c.offering_id)
            if offering is None or offering.academic_year not in years or c.completed_on > end:
                continue
            completers += 1
            synthetic += int(c.is_synthetic)
            placed += int(c.placed_role == role)
        return completers, placed, synthetic, years

    def _absorption(self, cells: list[tuple], quarter: str) -> dict[tuple, Component]:
        parts = {}
        for cell in cells:
            role, district = cell
            completers, placed, synthetic, years = self.absorption_counts(role, district, quarter)
            if not completers:
                parts[cell] = Component(
                    "absorption", False, note="no trainees completed a course for this role here"
                )
                continue
            parts[cell] = Component(
                "absorption",
                True,
                value=100 * placed / completers,
                raw={"completers": completers, "placed_in_role": placed, "cohorts": years},
                records=completers,
                synthetic_records=synthetic,
            )
        return parts

    # ------------------------------------------------------------------ combine
    def _combine(
        self, level: str, cell: tuple, quarter: str, parts: list[Component]
    ) -> DemandResult:
        available = {p.name for p in parts if p.available}
        weights = self.settings.weights.renormalized(available)
        score = 0.0
        for part in parts:
            part.weight = self.weights[part.name]
            part.effective_weight = weights.get(part.name, 0.0)
            if part.available and part.value is not None:
                score += part.effective_weight * part.value
        records = sum(p.records for p in parts if p.available)
        types = sum(1 for p in parts if p.available and p.records > 0)
        return DemandResult(
            level,
            cell[0],
            cell[1],
            quarter,
            round(min(100.0, max(0.0, score)), 2),
            parts,
            confidence_of(types, records, self.config),
        )


def by_cell(results: list[DemandResult]) -> dict[tuple[uuid.UUID, uuid.UUID, str], DemandResult]:
    return {(r.item_id, r.district_id, r.quarter): r for r in results}


def history(results: list[DemandResult]) -> dict[tuple[uuid.UUID, uuid.UUID], list[DemandResult]]:
    out: dict[tuple[uuid.UUID, uuid.UUID], list[DemandResult]] = defaultdict(list)
    for r in sorted(results, key=lambda r: quarter_index(r.quarter)):
        out[(r.item_id, r.district_id)].append(r)
    return out
