"""Does the engine rediscover the planted synthetic patterns (docs/SYNTHETIC_DATA_SPEC.md)?

    results = validate(computation, config)     # list of (id, passed, message)

These checks read the ENGINE's outputs (demand scores, mismatch statuses, skill trends), not
the synthetic spec, so they fail if the engine stops finding what the data contains.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analytics.engine import Computation
from app.config import ProductConfig
from app.models.enums import MismatchStatus, TrendStatus


@dataclass(frozen=True)
class Finding:
    id: str
    passed: bool
    message: str


def validate(computation: Computation, config: ProductConfig) -> list[Finding]:
    inputs = computation.inputs
    quarters = inputs.quarters
    first, last = quarters[1], quarters[-1]  # the first quarter with a full growth window is later
    role = {r.code: r.id for r in inputs.roles.values()}
    district = {code: i for i, (code, _) in inputs.districts.items()}
    skill = {code: i for i, (code, _) in inputs.skills.items()}
    findings: list[Finding] = []

    def check(check_id: str, passed: bool, message: str) -> None:
        findings.append(Finding(check_id, passed, message))

    def score(role_code: str, district_code: str, quarter: str) -> float | None:
        result = computation.demand(role[role_code], district[district_code], quarter)
        return result.score if result else None

    nashik, kolhapur = "MH-NASHIK", "MH-KOLHAPUR"
    ev_roles = [r.code for r in inputs.sector_roles("EV")]
    for code in ev_roles:
        before, after = score(code, nashik, first), score(code, nashik, last)
        check(
            "NASHIK-EV-DEMAND",
            before is not None and after is not None and after > before,
            f"Nashik {code} demand {before} ({first}) -> {after} ({last})",
        )
        mismatch = computation.mismatch_for(role[code], district[nashik], last)
        check(
            "NASHIK-EV-SHORTAGE",
            mismatch is not None and mismatch.status == MismatchStatus.UNDERSUPPLIED,
            f"Nashik {code} {last}: supply "
            f"{mismatch.supply.trained_output if mismatch and mismatch.supply else None} "
            f"/ openings {round(mismatch.openings.value or 0, 1) if mismatch else None} -> "
            f"{mismatch.status.value if mismatch else None}",
        )
    for code in ("ev-diagnostics", "battery-management", "ev-charging-systems"):
        result = computation.skill(skill[code], district[nashik], last)
        check(
            "NASHIK-EV-SKILLS",
            result is not None
            and result.trend is not None
            and result.trend["status"] == TrendStatus.EMERGING.value,
            f"Nashik {code}: {result.trend['status'] if result and result.trend else None} "
            f"(mentions {result.trend['window'] if result and result.trend else None})",
        )
    wireman = computation.mismatch_for(role["wireman"], district[kolhapur], last)
    check(
        "KOLHAPUR-OVERSUPPLY",
        wireman is not None and wireman.status == MismatchStatus.OVERSUPPLIED,
        f"Kolhapur wireman {last}: supply "
        f"{wireman.supply.trained_output if wireman and wireman.supply else None} "
        f"/ openings {round(wireman.openings.value or 0, 1) if wireman else None} = ratio "
        f"{wireman.ratio if wireman else None} -> {wireman.status.value if wireman else None}",
    )
    before, after = score("wireman", kolhapur, first), score("wireman", kolhapur, last)
    check(
        "KOLHAPUR-LOWER-DEMAND",
        before is not None and after is not None and after < before,
        f"Kolhapur wireman demand {before} ({first}) -> {after} ({last})",
    )
    window = quarters[-config.scoring.trend.window_quarters :]
    for code, district_id in district.items():
        series = [score("motor-rewinder", code, q) for q in window]
        check(
            "MOTOR-REWINDING-DECLINE",
            all(s is not None for s in series)
            and all(b < a for a, b in zip(series, series[1:], strict=False)),
            f"{code} motor-rewinder demand {series}",
        )
        result = computation.skill(skill["motor-rewinding"], district_id, last)
        check(
            "MOTOR-REWINDING-DECLINE",
            result is not None
            and result.trend is not None
            and result.trend["status"] == TrendStatus.DECLINING.value,
            f"{code} Motor Rewinding skill: "
            f"{result.trend['status'] if result and result.trend else None}",
        )
    return findings
