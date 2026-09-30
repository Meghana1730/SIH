"""Estimated openings, supply/openings ratio, status and district mismatch.

    openings(r, d, t) = postings for r in d in the last `openings.window_quarters` quarters
                        / coverage factor of the role                  (an ESTIMATE)
    R = supply / openings      (supply of the academic year completed by the end of t)
    UNDER_SUPPLIED  R < mismatch.undersupplied_below   (0.7)
    BALANCED        undersupplied_below <= R <= oversupplied_above
    OVER_SUPPLIED   R > mismatch.oversupplied_above    (1.5)
    INSUFFICIENT_DATA  no postings in the window, or no course data for the district/year

District mismatch = demand-weighted mean of |ln(R)| over the district's roles with a ratio
(R below mismatch.district_ratio_floor counts as the floor). 0 = every role balanced at
R = 1; larger = further from balance in either direction.

The coverage factors are MODELLING ASSUMPTIONS (config/scoring.yaml), never official
statistics, and every result shows the one it used.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Any

from app.analytics.demand import DemandResult
from app.analytics.inputs import Inputs
from app.analytics.supply import SupplyResult, academic_year_for, role_supply
from app.config import ProductConfig
from app.config.base import quarter_index
from app.models.enums import Confidence, MismatchStatus

CONFIDENCE_ORDER = [Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH]


@dataclass
class Openings:
    value: float | None  # annual openings estimate
    postings: int  # postings in the window
    synthetic_postings: int
    quarters_used: list[str]
    factor: float
    factor_label: str
    annualised: bool  # fewer quarters than the window were available

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_annual_openings": None if self.value is None else round(self.value, 2),
            "postings_in_window": self.postings,
            "quarters": self.quarters_used,
            "coverage_factor": self.factor,
            "coverage_factor_type": self.factor_label,
            "annualised_from_fewer_quarters": self.annualised,
        }


def estimate_openings(
    inputs: Inputs, config: ProductConfig, role: uuid.UUID, district: uuid.UUID, quarter: str
) -> Openings:
    settings = config.scoring.demand.openings
    upto = [q for q in inputs.quarters if quarter_index(q) <= quarter_index(quarter)]
    window = upto[-settings.window_quarters :]
    postings = synthetic = 0
    for q in window:
        counts = inputs.role_postings.get((role, district, q))
        if counts:
            postings += counts.total
            synthetic += counts.synthetic
    factor, label = settings.factor_for(inputs.roles[role].code)
    if district not in inputs.posting_districts or not window:
        return Openings(None, 0, 0, window, factor, label, False)
    annualised = len(window) < settings.window_quarters
    per_year = postings * (settings.window_quarters / len(window))
    return Openings(per_year / factor, postings, synthetic, window, factor, label, annualised)


def classify(ratio: float | None, config: ProductConfig) -> MismatchStatus:
    if ratio is None:
        return MismatchStatus.INSUFFICIENT_DATA
    limits = config.scoring.mismatch
    if ratio < limits.undersupplied_below:
        return MismatchStatus.UNDERSUPPLIED
    if ratio > limits.oversupplied_above:
        return MismatchStatus.OVERSUPPLIED
    return MismatchStatus.BALANCED


@dataclass
class MismatchResult:
    role_id: uuid.UUID
    district_id: uuid.UUID
    quarter: str
    supply: SupplyResult | None
    openings: Openings
    ratio: float | None
    status: MismatchStatus
    demand: DemandResult | None

    @property
    def confidence(self) -> Confidence:
        levels = [Confidence.LOW if self.ratio is None else Confidence.HIGH]
        if self.supply is not None:
            levels.append(self.supply.confidence)
        if self.demand is not None:
            levels.append(self.demand.confidence)
        else:
            levels.append(Confidence.LOW)
        return min(levels, key=CONFIDENCE_ORDER.index)

    @property
    def synthetic_share(self) -> float:
        parts, weights = [], []
        if self.openings.postings:
            parts.append(self.openings.synthetic_postings / self.openings.postings)
            weights.append(self.openings.postings)
        if self.supply is not None and self.supply.offerings:
            parts.append(self.supply.synthetic_share)
            weights.append(len(self.supply.offerings))
        if not weights:
            return 0.0
        return round(sum(p * w for p, w in zip(parts, weights, strict=True)) / sum(weights), 4)


def mismatch_for(
    inputs: Inputs,
    config: ProductConfig,
    role: uuid.UUID,
    district: uuid.UUID,
    quarter: str,
    demand: DemandResult | None,
) -> MismatchResult:
    openings = estimate_openings(inputs, config, role, district, quarter)
    year = academic_year_for(quarter, {o.academic_year for o in inputs.offerings})
    supply = role_supply(inputs, config, role, district, year) if year else None
    ratio = None
    if supply is not None and supply.data_available and openings.value:
        ratio = round(supply.trained_output / openings.value, 4)
    return MismatchResult(
        role, district, quarter, supply, openings, ratio, classify(ratio, config), demand
    )


def district_mismatch(results: list[MismatchResult], config: ProductConfig) -> dict[str, Any]:
    """Demand-weighted mean |ln R| over roles with a ratio (and some demand)."""
    floor = config.scoring.mismatch.district_ratio_floor
    rows, total_weight, weighted = [], 0.0, 0.0
    for r in results:
        if r.ratio is None or r.demand is None or r.demand.score <= 0:
            continue
        distance = abs(math.log(max(r.ratio, floor)))
        total_weight += r.demand.score
        weighted += r.demand.score * distance
        rows.append((r, distance))
    score = weighted / total_weight if total_weight else None
    return {
        "mismatch_score": None if score is None else round(score, 4),
        "definition": "demand-weighted mean of |ln(supply / openings)| over the district's roles",
        "ratio_floor": floor,
        "roles_counted": len(rows),
        "roles": [
            {
                "role_id": str(r.role_id),
                "ratio": r.ratio,
                "status": r.status.value,
                "abs_log_ratio": round(d, 4),
                "demand_weight": r.demand.score if r.demand else None,
            }
            for r, d in sorted(rows, key=lambda x: -x[1])
        ],
    }
