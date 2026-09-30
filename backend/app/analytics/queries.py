"""Read the current pipeline run's results for the API, with their explanations.

Every returned item has the same explanation block:
    observed_inputs   the counts behind the number (postings, survey headcount, events,
                      completers/placed, offerings)
    estimated_values  numbers the engine estimated (demand score, openings, supply, ratio)
    assumptions       modelling assumptions used (weights, coverage factor, default rates ...)
    confidence        HIGH / MEDIUM / LOW (config/scoring.yaml `confidence`)
    reasons           plain-language reasons, ONLY those the stored evidence supports
    is_synthetic      True if any evidence is synthetic; synthetic_share = how much
"""

from __future__ import annotations

import math
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ProductConfig
from app.models import (
    DemandScore,
    District,
    JobRole,
    Mismatch,
    PipelineRun,
    Sector,
    Skill,
    SupplyEstimate,
)


def current_run(db: Session) -> PipelineRun | None:
    return db.scalar(select(PipelineRun).where(PipelineRun.is_current.is_(True)))


def data_label(share: float) -> str:
    if share >= 1:
        return "demo data (synthetic)"
    if share > 0:
        return "partly demo data (synthetic)"
    return "real data"


def explanation(row: Any, estimated: dict[str, Any]) -> dict[str, Any]:
    components = row.components_json or []
    evidence = row.evidence_json or []
    return {
        "observed_inputs": {
            c["name"]: c.get("observed") for c in components if c.get("observed") is not None
        },
        "estimated_values": estimated,
        "assumptions": [e for e in evidence if e.get("type") == "assumption"],
        "confidence": row.confidence,
        "reasons": [e for e in evidence if e.get("type") == "reason"],
        "is_synthetic": row.synthetic_share > 0,
        "synthetic_share": row.synthetic_share,
        "data_label": data_label(row.synthetic_share),
    }


def _labels(db: Session) -> tuple[dict, dict, dict]:
    districts = {d.id: d for d in db.scalars(select(District))}
    roles = {
        r.id: (r, code)
        for r, code in db.execute(
            select(JobRole, Sector.code).join(Sector, Sector.id == JobRole.sector_id)
        )
    }
    skills = {s.id: s for s in db.scalars(select(Skill))}
    return districts, roles, skills


def _role_ids(db: Session, sector: str | None, role: str | None) -> list[uuid.UUID] | None:
    if sector is None and role is None:
        return None
    query = select(JobRole.id).join(Sector, Sector.id == JobRole.sector_id)
    if sector:
        query = query.where(Sector.code == sector)
    if role:
        query = query.where(JobRole.code == role)
    return list(db.scalars(query))


def _district(d: District) -> dict[str, str]:
    return {"code": d.code, "name": d.name}


def demand_items(
    db: Session,
    run: PipelineRun,
    *,
    districts: list[uuid.UUID],
    quarter: str | None,
    sector: str | None = None,
    role: str | None = None,
    skill: str | None = None,
    level: str = "role",
) -> list[dict[str, Any]]:
    labels_d, labels_r, labels_s = _labels(db)
    query = select(DemandScore).where(
        DemandScore.pipeline_run_id == run.id, DemandScore.district_id.in_(districts)
    )
    if quarter:
        query = query.where(DemandScore.quarter == quarter)
    if level == "skill" or skill:
        query = query.where(DemandScore.skill_id.is_not(None))
        if skill:
            query = query.where(
                DemandScore.skill_id.in_(select(Skill.id).where(Skill.code == skill))
            )
    else:
        query = query.where(DemandScore.role_id.is_not(None))
        role_ids = _role_ids(db, sector, role)
        if role_ids is not None:
            query = query.where(DemandScore.role_id.in_(role_ids))
    items = []
    for row in db.scalars(query.order_by(DemandScore.quarter, DemandScore.score.desc())):
        item: dict[str, Any] = {
            "district": _district(labels_d[row.district_id]),
            "quarter": row.quarter,
        }
        if row.role_id is not None:
            role_row, sector_code = labels_r[row.role_id]
            item["role"] = {"code": role_row.code, "title": role_row.title, "sector": sector_code}
        else:
            s = labels_s[row.skill_id]
            item["skill"] = {"code": s.code, "name": s.name}
            item["trend_status"] = row.trend_status
            item["mention_count"] = row.mention_count
        item["demand_score"] = row.score
        estimated = {"demand_score": row.score}
        if row.estimated_openings is not None:
            estimated["estimated_annual_openings"] = row.estimated_openings
        item["components"] = [c for c in row.components_json if c.get("name") != "trend"]
        item.update(explanation(row, estimated))
        items.append(item)
    return items


def supply_items(
    db: Session,
    run: PipelineRun,
    *,
    districts: list[uuid.UUID],
    academic_year: str | None,
    sector: str | None = None,
    role: str | None = None,
) -> list[dict[str, Any]]:
    labels_d, labels_r, _ = _labels(db)
    query = select(SupplyEstimate).where(
        SupplyEstimate.pipeline_run_id == run.id, SupplyEstimate.district_id.in_(districts)
    )
    if academic_year:
        query = query.where(SupplyEstimate.academic_year == academic_year)
    role_ids = _role_ids(db, sector, role)
    if role_ids is not None:
        query = query.where(SupplyEstimate.role_id.in_(role_ids))
    items = []
    for row in db.scalars(
        query.order_by(SupplyEstimate.academic_year, SupplyEstimate.trained_output.desc())
    ):
        role_row, sector_code = labels_r[row.role_id]
        items.append(
            {
                "district": _district(labels_d[row.district_id]),
                "role": {"code": role_row.code, "title": role_row.title, "sector": sector_code},
                "academic_year": row.academic_year,
                "trained_output_per_year": row.trained_output,
                "formula": "sum over the role's courses of seats_filled x completion_rate",
                "offerings": row.components_json,
                "observed_inputs": {"offerings": row.components_json},
                "estimated_values": {"trained_output_per_year": row.trained_output},
                "assumptions": [e for e in row.evidence_json if e.get("type") == "assumption"],
                "confidence": row.confidence,
                "reasons": [],
                "is_synthetic": row.synthetic_share > 0,
                "synthetic_share": row.synthetic_share,
                "data_label": data_label(row.synthetic_share),
            }
        )
    return items


def mismatch_items(
    db: Session,
    run: PipelineRun,
    *,
    districts: list[uuid.UUID],
    quarter: str | None,
    sector: str | None = None,
    role: str | None = None,
    include_insufficient: bool = False,
) -> list[dict[str, Any]]:
    labels_d, labels_r, _ = _labels(db)
    query = select(Mismatch).where(
        Mismatch.pipeline_run_id == run.id, Mismatch.district_id.in_(districts)
    )
    if quarter:
        query = query.where(Mismatch.quarter == quarter)
    if not include_insufficient:
        query = query.where(Mismatch.status != "INSUFFICIENT_DATA")
    role_ids = _role_ids(db, sector, role)
    if role_ids is not None:
        query = query.where(Mismatch.role_id.in_(role_ids))
    demand = {
        (d.role_id, d.district_id, d.quarter): d.score
        for d in db.scalars(
            select(DemandScore).where(
                DemandScore.pipeline_run_id == run.id, DemandScore.role_id.is_not(None)
            )
        )
    }
    items = []
    for row in db.scalars(query.order_by(Mismatch.quarter, Mismatch.ratio)):
        role_row, sector_code = labels_r[row.role_id]
        score = demand.get((row.role_id, row.district_id, row.quarter))
        estimated = {
            "demand_score": score,
            "estimated_annual_openings": row.openings,
            "trained_output_per_year": row.supply,
            "ratio": row.ratio,
        }
        items.append(
            {
                "district": _district(labels_d[row.district_id]),
                "role": {"code": role_row.code, "title": role_row.title, "sector": sector_code},
                "quarter": row.quarter,
                "demand_score": score,
                "supply": row.supply,
                "estimated_openings": row.openings,
                "ratio": row.ratio,
                "status": row.status,
                **explanation(row, estimated),
            }
        )
    return items


def district_mismatch_item(
    db: Session, run: PipelineRun, district: District, quarter: str, config: ProductConfig
) -> dict[str, Any]:
    items = mismatch_items(db, run, districts=[district.id], quarter=quarter)
    floor = config.scoring.mismatch.district_ratio_floor
    weighted = total = 0.0
    shares = []
    for item in items:
        if item["ratio"] is None or not item["demand_score"]:
            continue
        distance = abs(math.log(max(item["ratio"], floor)))
        item["abs_log_ratio"] = round(distance, 4)
        weighted += item["demand_score"] * distance
        total += item["demand_score"]
        shares.append(item["synthetic_share"])
    score = round(weighted / total, 4) if total else None
    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    share = round(sum(shares) / len(shares), 4) if shares else 0.0
    return {
        "district": _district(district),
        "quarter": quarter,
        "mismatch_score": score,
        "definition": (
            "demand-weighted mean of |ln(supply / openings)| over the district's "
            "roles (0 = balanced)"
        ),
        "ratio_floor": floor,
        "status_counts": counts,
        "is_synthetic": share > 0,
        "synthetic_share": share,
        "data_label": data_label(share),
        "roles": sorted(items, key=lambda i: -(i.get("abs_log_ratio") or 0)),
    }
