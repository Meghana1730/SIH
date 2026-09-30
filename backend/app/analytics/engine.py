"""Run the whole engine: demand -> supply -> mismatch for every district and quarter, stored
as ONE pipeline run (the app reads the run marked is_current).

    summary = run_engine(db, config)          # the caller commits
    computation = compute(load_inputs(db, config), config)   # in memory, nothing stored

Each stored row keeps its explanation: components_json holds the observed inputs behind every
number, evidence_json holds the reasons (only those the evidence supports) and the
assumptions used, and synthetic_share says how much of the evidence is demo data. The run
points to a saved copy of config/scoring.yaml (scoring_config_version), so every number can
be traced to the settings that made it.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.analytics.demand import DemandEngine, DemandResult, by_cell
from app.analytics.explain import (
    demand_assumptions,
    demand_reasons,
    mismatch_assumptions,
    mismatch_reasons,
)
from app.analytics.inputs import Inputs, load_inputs
from app.analytics.mismatch import MismatchResult, district_mismatch, mismatch_for
from app.analytics.supply import SupplyResult, all_role_supply
from app.config import ProductConfig
from app.models import DemandScore, Mismatch, PipelineRun, ScoringConfigVersion, SupplyEstimate
from app.models.enums import RunStatus
from app.synthetic.timeline import shift_quarter


@dataclass
class Computation:
    inputs: Inputs
    role_demand: list[DemandResult]
    skill_demand: list[DemandResult]
    supply: list[SupplyResult]
    mismatch: list[MismatchResult]
    timings: dict[str, float] = field(default_factory=dict)

    def demand(self, role: uuid.UUID, district: uuid.UUID, quarter: str) -> DemandResult | None:
        return by_cell(self.role_demand).get((role, district, quarter))

    def skill(self, skill: uuid.UUID, district: uuid.UUID, quarter: str) -> DemandResult | None:
        return by_cell(self.skill_demand).get((skill, district, quarter))

    def mismatch_for(
        self, role: uuid.UUID, district: uuid.UUID, quarter: str
    ) -> MismatchResult | None:
        return next(
            (
                m
                for m in self.mismatch
                if (m.role_id, m.district_id, m.quarter) == (role, district, quarter)
            ),
            None,
        )

    def district_score(
        self, district: uuid.UUID, quarter: str, config: ProductConfig
    ) -> dict[str, Any]:
        rows = [m for m in self.mismatch if m.district_id == district and m.quarter == quarter]
        return district_mismatch(rows, config)


def compute(inputs: Inputs, config: ProductConfig) -> Computation:
    timings: dict[str, float] = {}
    started = time.perf_counter()
    engine = DemandEngine(inputs, config)
    role_demand: list[DemandResult] = []
    skill_demand: list[DemandResult] = []
    for quarter in inputs.quarters:
        role_demand += engine.roles(quarter)
        skill_demand += engine.skills(quarter)
    timings["demand_seconds"] = round(time.perf_counter() - started, 3)
    started = time.perf_counter()
    supply = all_role_supply(inputs, config)
    timings["supply_seconds"] = round(time.perf_counter() - started, 3)
    started = time.perf_counter()
    cells = by_cell(role_demand)
    mismatch = [
        mismatch_for(inputs, config, role, district, quarter, cells.get((role, district, quarter)))
        for quarter in inputs.quarters
        for district in inputs.districts
        for role in inputs.roles
    ]
    timings["mismatch_seconds"] = round(time.perf_counter() - started, 3)
    return Computation(inputs, role_demand, skill_demand, supply, mismatch, timings)


# --------------------------------------------------------------------------- payloads
def demand_payload(
    result: DemandResult, computation: Computation, config: ProductConfig
) -> tuple[list, list]:
    lookup = computation.demand if result.level == "role" else computation.skill
    earlier = lookup(result.item_id, result.district_id, shift_quarter(result.quarter, -2))
    reasons = demand_reasons(result, earlier, computation.inputs, config)
    components = [c.to_dict() for c in result.components]
    if result.trend is not None:
        components.append({"name": "trend", "observed": result.trend})
    return components, reasons + demand_assumptions(result, config)


def mismatch_payload(
    result: MismatchResult, computation: Computation, config: ProductConfig
) -> tuple[list, list]:
    supply = result.supply
    components: list[dict[str, Any]] = [
        {"name": "openings", "estimated": True, "observed": result.openings.to_dict()},
        {
            "name": "supply",
            "estimated": True,
            "observed": {
                "academic_year": supply.academic_year if supply else None,
                "trained_output_per_year": supply.trained_output if supply else None,
                "course_data_available": supply.data_available if supply else False,
                "offerings": supply.offerings if supply else [],
            },
        },
        {
            "name": "demand",
            "observed": (
                {"score": result.demand.score, "confidence": result.demand.confidence.value}
                if result.demand
                else None
            ),
        },
    ]
    reasons = mismatch_reasons(result, computation.inputs)
    if result.demand is not None:
        reasons = demand_payload(result.demand, computation, config)[1] + reasons
        reasons = [r for r in reasons if r["type"] == "reason"]
    return components, reasons + mismatch_assumptions(result, config)


# --------------------------------------------------------------------------- storing
def _config_version(db: Session, config: ProductConfig) -> ScoringConfigVersion:
    sha = config.scoring_sha256
    existing = db.scalar(
        select(ScoringConfigVersion).where(ScoringConfigVersion.config_sha256 == sha)
    )
    if existing is not None:
        return existing
    label = config.scoring.version
    if (
        db.scalar(select(ScoringConfigVersion.id).where(ScoringConfigVersion.version == label))
        is not None
    ):
        label = f"{label}+{sha[:8]}"  # the file changed without a new version number
    version = ScoringConfigVersion(
        version=label,
        config_sha256=sha,
        config_yaml=(config.config_dir / "scoring.yaml").read_text(encoding="utf-8"),
        notes="recorded automatically by an analytics run (not an approved/active version)",
    )
    db.add(version)
    db.flush()
    return version


@dataclass
class RunSummary:
    run_id: uuid.UUID
    quarter: str
    demand_rows: int
    skill_rows: int
    supply_rows: int
    mismatch_rows: int
    computation: Computation


def run_engine(
    db: Session, config: ProductConfig, triggered_by: uuid.UUID | None = None
) -> RunSummary:
    started_at = datetime.now(UTC)
    inputs = load_inputs(db, config)
    computation = compute(inputs, config)
    version = _config_version(db, config)
    run = PipelineRun(
        status=RunStatus.RUNNING.value,
        quarter=inputs.quarters[-1],
        config_version_id=version.id,
        triggered_by_id=triggered_by,
        started_at=started_at,
    )
    db.add(run)
    db.flush()
    rows: list[Any] = []
    for result in computation.role_demand + computation.skill_demand:
        components, evidence = demand_payload(result, computation, config)
        openings = None
        if result.level == "role":
            match = computation.mismatch_for(result.item_id, result.district_id, result.quarter)
            openings = match.openings.value if match is not None else None
        rows.append(
            DemandScore(
                pipeline_run_id=run.id,
                district_id=result.district_id,
                quarter=result.quarter,
                role_id=result.item_id if result.level == "role" else None,
                skill_id=result.item_id if result.level == "skill" else None,
                score=result.score,
                estimated_openings=None if openings is None else round(openings, 2),
                mention_count=result.mention_count,
                trend_status=result.trend["status"] if result.trend else None,
                confidence=result.confidence.value,
                synthetic_share=result.synthetic_share,
                components_json=components,
                evidence_json=evidence,
            )
        )
    for supply in computation.supply:
        rows.append(
            SupplyEstimate(
                pipeline_run_id=run.id,
                district_id=supply.district_id,
                role_id=supply.role_id,
                academic_year=supply.academic_year,
                trained_output=supply.trained_output,
                confidence=supply.confidence.value,
                synthetic_share=supply.synthetic_share,
                components_json=supply.offerings,
                evidence_json=[{"type": "assumption", **a} for a in supply.assumptions(config)],
            )
        )
    for result in computation.mismatch:
        components, evidence = mismatch_payload(result, computation, config)
        rows.append(
            Mismatch(
                pipeline_run_id=run.id,
                district_id=result.district_id,
                role_id=result.role_id,
                quarter=result.quarter,
                supply=result.supply.trained_output if result.supply else 0.0,
                openings=round(result.openings.value or 0.0, 2),
                ratio=result.ratio,
                status=result.status.value,
                confidence=result.confidence.value,
                synthetic_share=result.synthetic_share,
                components_json=components,
                evidence_json=evidence,
            )
        )
    db.add_all(rows)
    run.status = RunStatus.SUCCEEDED.value
    run.finished_at = datetime.now(UTC)
    run.step_timings_json = computation.timings
    db.execute(update(PipelineRun).where(PipelineRun.is_current.is_(True)).values(is_current=False))
    db.flush()
    run.is_current = True
    db.flush()
    return RunSummary(
        run.id,
        run.quarter,
        len(computation.role_demand),
        len(computation.skill_demand),
        len(computation.supply),
        len(computation.mismatch),
        computation,
    )
