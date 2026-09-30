"""Plain-language reasons and the explanation block for every result.

A reason is produced ONLY when the stored evidence supports it (a real rise in postings, a
real rise in survey headcount, an event in the data, a supply/openings gap), and it says
whether that evidence is synthetic. No reason is ever written from general knowledge.
"""

from __future__ import annotations

from typing import Any

from app.analytics.demand import DemandResult
from app.analytics.inputs import Inputs
from app.analytics.mismatch import MismatchResult
from app.config import ProductConfig
from app.models.enums import MismatchStatus, TrendStatus

GROWTH_WORTH_MENTIONING = 0.10  # below +/-10 % a change is not presented as a reason


def _reason(code: str, text: str, is_synthetic: bool, **evidence: Any) -> dict[str, Any]:
    return {
        "type": "reason",
        "code": code,
        "text": text,
        "is_synthetic": is_synthetic,
        "evidence": evidence,
    }


def demand_reasons(
    demand: DemandResult,
    earlier: DemandResult | None,
    inputs: Inputs,
    config: ProductConfig,
) -> list[dict[str, Any]]:
    """`earlier`: the same cell two quarters before (for survey changes)."""
    reasons = []
    name = _name(demand, inputs)
    district = inputs.districts[demand.district_id][1]
    postings = demand.component("postings")
    if postings is not None and postings.available and "growth" in postings.raw:
        growth = postings.raw["growth"]
        half = postings.raw["window_quarters"] // 2
        before, after = postings.raw["earlier_postings"], postings.raw["recent_postings"]
        if growth >= GROWTH_WORTH_MENTIONING:
            reasons.append(
                _reason(
                    "postings_increased",
                    f"{_postings_label(demand, name)} in {district} rose from {before} to {after} "
                    f"(last {half} quarters vs the {half} before).",
                    postings.synthetic_records > 0,
                    earlier=before,
                    recent=after,
                    growth=growth,
                )
            )
        elif growth <= -GROWTH_WORTH_MENTIONING:
            reasons.append(
                _reason(
                    "postings_decreased",
                    f"{_postings_label(demand, name)} in {district} fell from {before} to {after} "
                    f"(last {half} quarters vs the {half} before).",
                    postings.synthetic_records > 0,
                    earlier=before,
                    recent=after,
                    growth=growth,
                )
            )
    survey = demand.component("employer_survey")
    past = earlier.component("employer_survey") if earlier is not None else None
    if survey is not None and survey.available and past is not None and past.available:
        now, before = survey.raw["headcount"], past.raw["headcount"]
        noun = "people" if demand.level == "role" else "employers naming it"
        if now > before:
            reasons.append(
                _reason(
                    "employer_demand_increased",
                    f"Employers surveyed in {district} asked for {now} {noun} for {name} in their "
                    f"latest answers, up from {before} two quarters earlier.",
                    survey.synthetic_records > 0,
                    now=now,
                    two_quarters_earlier=before,
                )
            )
        elif now < before:
            reasons.append(
                _reason(
                    "employer_demand_decreased",
                    f"Employers surveyed in {district} asked for {now} {noun} for {name}, down "
                    f"from {before} two quarters earlier.",
                    survey.synthetic_records > 0,
                    now=now,
                    two_quarters_earlier=before,
                )
            )
    events = demand.component("growth_events")
    if events is not None and events.available:
        for event in events.raw["events"]:
            label = "" if "synthetic" in event["title"].lower() else (
                " (synthetic)" if event["is_synthetic"] else ""
            )
            if event["is_simulated"]:
                label += ", a simulated event,"
            reasons.append(
                _reason(
                    "industry_event",
                    f"{event['title']}{label} is expected to add about "
                    f"{event['jobs_for_role']:.0f} "
                    f"{name} jobs in {district} in {', '.join(event['quarters'])}.",
                    event["is_synthetic"],
                    **{
                        k: event[k]
                        for k in (
                            "event_id",
                            "expected_jobs",
                            "realization_factor",
                            "role_share",
                            "split",
                        )
                    },
                )
            )
    absorption = demand.component("absorption")
    if absorption is not None and absorption.available:
        rate = absorption.value / 100
        low = config.scoring.course_health.flags.low_placement_rate_below
        if rate < low:
            text = f"Only {rate:.0%} of recent local trainees for {name} were placed in this role"
        else:
            text = f"{rate:.0%} of recent local trainees for {name} were placed in this role"
        reasons.append(
            _reason(
                "absorption",
                f"{text} ({absorption.raw['placed_in_role']} of {absorption.raw['completers']}).",
                absorption.synthetic_records > 0,
                **absorption.raw,
            )
        )
    if demand.trend is not None and demand.trend["status"] != TrendStatus.STABLE.value:
        window = demand.trend["window"]
        if demand.trend["status"] == TrendStatus.DECLINING.value:
            text = (
                f"Mentions of {name} in {district} job ads fell "
                f"{demand.trend['consecutive_drops']} "
                f"quarters in a row ({' -> '.join(map(str, window))}): DECLINING."
            )
        else:
            text = (
                f"Mentions of {name} in {district} job ads grew "
                f"{demand.trend['growth']:+.0%} ({' -> '.join(map(str, window))}): EMERGING."
            )
        reasons.append(
            _reason(
                f"skill_{demand.trend['status'].lower()}",
                text,
                (postings.synthetic_records > 0) if postings else False,
                **demand.trend,
            )
        )
    return reasons


def _postings_label(demand: DemandResult, name: str) -> str:
    return f"{name} job postings" if demand.level == "role" else f"Job postings naming {name}"


def _name(demand: DemandResult, inputs: Inputs) -> str:
    if demand.level == "role":
        return inputs.roles[demand.item_id].title
    return inputs.skills[demand.item_id][1]


def mismatch_reasons(result: MismatchResult, inputs: Inputs) -> list[dict[str, Any]]:
    role = inputs.roles[result.role_id].title
    district = inputs.districts[result.district_id][1]
    supply = result.supply
    openings = result.openings
    synthetic = result.synthetic_share > 0
    if result.status == MismatchStatus.UNDERSUPPLIED and supply is not None:
        if supply.trained_output == 0:
            text = (
                f"No course in {district} trains people for {role} ({supply.academic_year}), "
                f"against about {openings.value:.0f} estimated openings a year."
            )
        else:
            text = (
                f"Local training supply for {role} ({supply.trained_output:.0f} trained a year) is "
                f"below the estimated openings ({openings.value:.0f} a year)."
            )
        return [_reason("training_supply_low", text, synthetic, ratio=result.ratio)]
    if result.status == MismatchStatus.OVERSUPPLIED and supply is not None:
        return [
            _reason(
                "training_supply_high",
                f"Local training supply for {role} ({supply.trained_output:.0f} trained a year) is "
                f"{result.ratio:.1f} times the estimated openings ({openings.value:.0f} a year).",
                synthetic,
                ratio=result.ratio,
            )
        ]
    if result.status == MismatchStatus.BALANCED:
        return [
            _reason(
                "balanced",
                f"Training supply for {role} in {district} is within the balanced range "
                f"(ratio {result.ratio:.2f}).",
                synthetic,
                ratio=result.ratio,
            )
        ]
    return []


def demand_assumptions(demand: DemandResult, config: ProductConfig) -> list[dict[str, Any]]:
    settings = config.scoring.demand
    missing = [c.name for c in demand.components if not c.available]
    items = [
        {
            "name": "demand weights",
            "value": {c.name: c.weight for c in demand.components},
            "effective": {c.name: round(c.effective_weight, 4) for c in demand.components},
            "source": "config/scoring.yaml demand.weights",
            **(
                {"note": f"no data for {', '.join(missing)}: remaining weights renormalised"}
                if missing
                else {}
            ),
        },
        {
            "name": "posting signal",
            "value": (
                f"{settings.posting_signal.volume_weight} x percentile(log(1+postings)) + "
                f"{settings.posting_signal.growth_weight} x percentile(growth clipped to "
                f"[{settings.posting_signal.growth_min}, {settings.posting_signal.growth_max}])"
            ),
            "source": "config/scoring.yaml demand.posting_signal",
        },
    ]
    if demand.component("employer_survey") is not None:
        items.append(
            {
                "name": "survey recency half-life (quarters)",
                "value": settings.survey.half_life_quarters,
                "source": "config/scoring.yaml demand.survey",
            }
        )
    if demand.level == "role":
        impact = config.scoring.event_impact
        items.append(
            {
                "name": "event impact",
                "value": (
                    f"jobs x realisation factor (default {impact.default_realization_factor}), "
                    f"spread over quarters +{impact.lag_start_quarter}..+{impact.lag_end_quarter}; "
                    "counted if they land in the next "
                    f"{settings.growth_events.lookahead_quarters} quarters"
                ),
                "source": "config/scoring.yaml event_impact, demand.growth_events",
            }
        )
    return [{"type": "assumption", **item} for item in items]


def mismatch_assumptions(result: MismatchResult, config: ProductConfig) -> list[dict[str, Any]]:
    limits = config.scoring.mismatch
    items = [
        {
            "name": "openings coverage factor",
            "value": result.openings.factor,
            "kind": result.openings.factor_label,
            "source": (
                "config/scoring.yaml demand.openings (modelling assumption, not an "
                "official statistic)"
            ),
        },
        {
            "name": "status thresholds",
            "value": {
                "under_supplied_below": limits.undersupplied_below,
                "over_supplied_above": limits.oversupplied_above,
            },
            "source": "config/scoring.yaml mismatch",
        },
    ]
    if result.openings.annualised:
        items.append(
            {
                "name": "annualised openings",
                "value": (
                    f"only {len(result.openings.quarters_used)} quarters of postings; "
                    "scaled to a year"
                ),
                "source": "app/analytics/mismatch.py",
            }
        )
    if result.supply is not None:
        items += result.supply.assumptions(config)
    return [{"type": "assumption", **item} for item in items]
