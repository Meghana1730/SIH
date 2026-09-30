"""Training supply: people trained per year = seats_filled x completion_rate.

When an offering has no completion rate, supply.default_completion_rate (0.8) is used. That is
a MODELLING ASSUMPTION and every result that used it says so.

A course counts as supply for its PRIMARY role (course_role.is_primary); its secondary roles
are other jobs graduates move into and are not counted twice (docs/SYNTHETIC_DATA_SPEC.md §6).
Supply can be grouped by district, institute, course, role or skill (a skill is supplied by
every course that teaches it).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.analytics.inputs import Inputs, OfferingInfo
from app.config import ProductConfig
from app.models.enums import Confidence
from app.synthetic.timeline import quarter_end


def academic_year_for(quarter: str, years: set[str]) -> str | None:
    """The most recent academic year whose cohort had completed (31 July) by the end of the
    quarter, e.g. 2026Q3 -> '2025-26'."""
    end = quarter_end(quarter)
    done = sorted(y for y in years if date(int(y[:4]) + 1, 7, 31) <= end)
    return done[-1] if done else None


@dataclass
class SupplyResult:
    district_id: uuid.UUID
    role_id: uuid.UUID | None
    academic_year: str
    trained_output: float
    offerings: list[dict[str, Any]] = field(default_factory=list)
    default_completion_used: bool = False
    data_available: bool = True  # False: no course data for the district and year

    @property
    def confidence(self) -> Confidence:
        if not self.data_available:
            return Confidence.LOW
        return Confidence.MEDIUM if self.default_completion_used else Confidence.HIGH

    @property
    def synthetic_share(self) -> float:
        if not self.offerings:
            return 0.0
        return round(sum(o["is_synthetic"] for o in self.offerings) / len(self.offerings), 4)

    def assumptions(self, config: ProductConfig) -> list[dict[str, Any]]:
        items = [
            {
                "name": "counting rule",
                "value": "a course counts for its primary role only",
                "source": "docs/SYNTHETIC_DATA_SPEC.md §6",
            }
        ]
        if self.default_completion_used:
            items.append(
                {
                    "name": "default completion rate",
                    "value": config.scoring.supply.default_completion_rate,
                    "source": (
                        "config/scoring.yaml supply.default_completion_rate "
                        "(modelling assumption)"
                    ),
                }
            )
        return items


def offering_output(offering: OfferingInfo, config: ProductConfig) -> dict[str, Any]:
    default = config.scoring.supply.default_completion_rate
    rate = offering.completion_rate
    used_default = rate is None
    rate = default if rate is None else rate
    filled = offering.seats_filled or 0
    return {
        "offering_id": str(offering.id),
        "institute": offering.institute_code,
        "institute_name": offering.institute_name,
        "course": offering.course_code,
        "course_name": offering.course_name,
        "academic_year": offering.academic_year,
        "seats": offering.seats,
        "seats_filled": filled,
        "completion_rate": round(rate, 4),
        "completion_rate_is_default": used_default,
        "trained_output": round(filled * rate, 2),
        "is_synthetic": offering.is_synthetic,
    }


def role_supply(
    inputs: Inputs, config: ProductConfig, role: uuid.UUID, district: uuid.UUID, year: str
) -> SupplyResult:
    offerings = [
        o for o in inputs.offerings if o.district_id == district and o.academic_year == year
    ]
    result = SupplyResult(district, role, year, 0.0, data_available=bool(offerings))
    for offering in offerings:
        if offering.primary_role != role:
            continue
        row = offering_output(offering, config)
        result.offerings.append(row)
        result.trained_output += row["trained_output"]
        result.default_completion_used |= row["completion_rate_is_default"]
    result.trained_output = round(result.trained_output, 2)
    return result


def academic_years(inputs: Inputs) -> list[str]:
    return sorted({o.academic_year for o in inputs.offerings})


def all_role_supply(inputs: Inputs, config: ProductConfig) -> list[SupplyResult]:
    """Supply for every role x district x academic year with course data in that district."""
    results = []
    for year in academic_years(inputs):
        districts = {o.district_id for o in inputs.offerings if o.academic_year == year}
        for district in sorted(districts, key=inputs.district_code):
            for role in inputs.roles:
                results.append(role_supply(inputs, config, role, district, year))
    return results


GROUPS = ("district", "institute", "course", "role", "skill")


def supply_breakdown(
    inputs: Inputs,
    config: ProductConfig,
    group_by: str,
    year: str,
    districts: set[uuid.UUID] | None = None,
) -> list[dict[str, Any]]:
    """Trained output per group for one academic year. Skill supply counts every course
    that teaches the skill (any band)."""
    if group_by not in GROUPS:
        raise ValueError(f"group_by must be one of {GROUPS}")
    totals: dict[tuple, dict[str, Any]] = {}
    for offering in inputs.offerings:
        if offering.academic_year != year or (
            districts is not None and offering.district_id not in districts
        ):
            continue
        row = offering_output(offering, config)
        district_code = inputs.district_code(offering.district_id)
        if group_by == "skill":
            keys = [
                (district_code, inputs.skills[s][0], inputs.skills[s][1])
                for s in offering.skills
                if s in inputs.skills
            ]
        elif group_by == "role":
            if offering.primary_role is None:
                continue
            role = inputs.roles[offering.primary_role]
            keys = [(district_code, role.code, role.title)]
        elif group_by == "institute":
            keys = [(district_code, offering.institute_code, offering.institute_name)]
        elif group_by == "course":
            keys = [(district_code, offering.course_code, offering.course_name)]
        else:
            keys = [(district_code, district_code, inputs.districts[offering.district_id][1])]
        for key in keys:
            entry = totals.setdefault(
                key,
                {
                    "district": key[0],
                    "group_by": group_by,
                    "key": key[1],
                    "label": key[2],
                    "academic_year": year,
                    "trained_output": 0.0,
                    "offerings": [],
                    "default_completion_used": False,
                    "synthetic_offerings": 0,
                },
            )
            entry["trained_output"] = round(entry["trained_output"] + row["trained_output"], 2)
            entry["offerings"].append(row)
            entry["default_completion_used"] |= row["completion_rate_is_default"]
            entry["synthetic_offerings"] += int(row["is_synthetic"])
    out = []
    for entry in sorted(totals.values(), key=lambda e: (e["district"], e["key"])):
        n = len(entry["offerings"])
        entry["is_synthetic"] = entry["synthetic_offerings"] > 0
        entry["synthetic_share"] = round(entry.pop("synthetic_offerings") / n, 4) if n else 0.0
        entry["assumptions"] = (
            [
                {
                    "name": "default completion rate",
                    "value": config.scoring.supply.default_completion_rate,
                    "source": "config/scoring.yaml (modelling assumption)",
                }
            ]
            if entry["default_completion_used"]
            else []
        )
        out.append(entry)
    return out


def skill_supply_by_district(
    inputs: Inputs, config: ProductConfig, year: str
) -> dict[tuple[str, str], float]:
    """(district code, skill code) -> trained output per year."""
    out: dict[tuple[str, str], float] = defaultdict(float)
    for row in supply_breakdown(inputs, config, "skill", year):
        out[(row["district"], row["key"])] += row["trained_output"]
    return dict(out)
