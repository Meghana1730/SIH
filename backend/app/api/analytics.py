"""Demand, supply and mismatch results with explanations (docs/07-demand-supply-mismatch.md).

GET  /analytics/demand                         role (or ?level=skill / ?skill=) demand scores
GET  /analytics/demand/{district}              the same for one district
GET  /analytics/supply                         trained people per year (?group_by=...)
GET  /analytics/mismatch                       supply / openings per role
GET  /analytics/districts/{district}/mismatch  district mismatch score + its roles
POST /analytics/run                            recompute everything (admin)

Filters: district, sector, role, skill, quarter (default: the run's latest quarter).
Results come from the current pipeline run; users only see districts in their scope.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.analytics.engine import run_engine
from app.analytics.inputs import load_inputs
from app.analytics.queries import (
    current_run,
    demand_items,
    district_mismatch_item,
    mismatch_items,
    supply_items,
)
from app.analytics.supply import GROUPS, academic_years, supply_breakdown
from app.api.deps import DbSession, error, require_roles
from app.config import get_config
from app.models import AppUser, District, PipelineRun
from app.models.enums import UserRole
from app.services.access import district_scope
from app.services.audit import record_audit

router = APIRouter(prefix="/analytics", tags=["analytics"])

Viewer = Annotated[
    AppUser,
    Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.STATE_OFFICER,
            UserRole.DISTRICT_OFFICER,
            UserRole.SSC_REVIEWER,
            UserRole.INSTITUTE_ADMIN,
            UserRole.EMPLOYER,
        )
    ),
]
AdminUser = Annotated[AppUser, Depends(require_roles(UserRole.ADMIN))]
Quarter = Annotated[str | None, Query(pattern=r"^[0-9]{4}Q[1-4]$")]


def _run(db: DbSession) -> PipelineRun:
    run = current_run(db)
    if run is None:
        raise error(
            404, "NO_RESULTS", "No analytics results yet. Run: python -m app.cli.analytics run"
        )
    return run


def _districts(db: DbSession, user: AppUser, district: str | None) -> list:
    """District ids the user may see, optionally narrowed to one code (403 if outside)."""
    allowed = {d.code: d.id for d in db.scalars(select(District).where(district_scope(user)))}
    if district is None:
        return list(allowed.values())
    exists = db.scalar(select(District.id).where(District.code == district))
    if exists is None:
        raise error(404, "NOT_FOUND", f"No district {district}.")
    if district not in allowed:
        raise error(403, "FORBIDDEN_SCOPE", "This district is outside your area of access.")
    return [allowed[district]]


def _page(run: PipelineRun, quarter: str | None, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "pipeline_run_id": str(run.id),
        "computed_at": run.finished_at.isoformat() if run.finished_at else None,
        "quarter": quarter,
        "count": len(items),
        "items": items,
    }


@router.get("/demand")
def demand(
    user: Viewer,
    db: DbSession,
    district: str | None = None,
    sector: str | None = None,
    role: str | None = None,
    skill: str | None = None,
    quarter: Quarter = None,
    level: Annotated[str, Query(pattern="^(role|skill)$")] = "role",
) -> dict[str, Any]:
    run = _run(db)
    quarter = quarter or run.quarter
    items = demand_items(
        db,
        run,
        districts=_districts(db, user, district),
        quarter=quarter,
        sector=sector,
        role=role,
        skill=skill,
        level=level,
    )
    return _page(run, quarter, items)


@router.get("/demand/{district}")
def demand_for_district(
    district: str,
    user: Viewer,
    db: DbSession,
    sector: str | None = None,
    role: str | None = None,
    skill: str | None = None,
    quarter: Quarter = None,
    level: Annotated[str, Query(pattern="^(role|skill)$")] = "role",
) -> dict[str, Any]:
    return demand(user, db, district, sector, role, skill, quarter, level)


@router.get("/supply")
def supply(
    user: Viewer,
    db: DbSession,
    district: str | None = None,
    sector: str | None = None,
    role: str | None = None,
    academic_year: Annotated[str | None, Query(pattern=r"^[0-9]{4}-[0-9]{2}$")] = None,
    group_by: Annotated[str, Query(description=f"one of {', '.join(GROUPS)}")] = "role",
) -> dict[str, Any]:
    """Trained people per year = seats_filled x completion_rate (0.8 when unknown: an
    assumption). group_by=role reads the stored run; district / institute / course / skill
    are computed from the course offerings with the same formula."""
    run = _run(db)
    districts = _districts(db, user, district)
    if group_by == "role":
        items = supply_items(
            db, run, districts=districts, academic_year=academic_year, sector=sector, role=role
        )
        return _page(run, None, items)
    if group_by not in GROUPS:
        raise error(400, "BAD_REQUEST", f"group_by must be one of {', '.join(GROUPS)}")
    inputs = load_inputs(db, get_config())
    years = academic_years(inputs)
    year = academic_year or (years[-1] if years else None)
    items = supply_breakdown(inputs, get_config(), group_by, year, set(districts)) if year else []
    return {**_page(run, None, items), "academic_year": year, "computed_now": True}


@router.get("/mismatch")
def mismatch(
    user: Viewer,
    db: DbSession,
    district: str | None = None,
    sector: str | None = None,
    role: str | None = None,
    quarter: Quarter = None,
    include_insufficient: bool = False,
) -> dict[str, Any]:
    run = _run(db)
    quarter = quarter or run.quarter
    items = mismatch_items(
        db,
        run,
        districts=_districts(db, user, district),
        quarter=quarter,
        sector=sector,
        role=role,
        include_insufficient=include_insufficient,
    )
    return _page(run, quarter, items)


@router.get("/districts/{district}/mismatch")
def district_mismatch(
    district: str, user: Viewer, db: DbSession, quarter: Quarter = None
) -> dict[str, Any]:
    run = _run(db)
    (district_id,) = _districts(db, user, district)
    row = db.get(District, district_id)
    quarter = quarter or run.quarter
    return {
        "pipeline_run_id": str(run.id),
        **district_mismatch_item(db, run, row, quarter, get_config()),
    }


@router.post("/run")
def run_now(admin: AdminUser, db: DbSession) -> dict[str, Any]:
    summary = run_engine(db, get_config(), triggered_by=admin.id)
    db.commit()
    record_audit(
        db, "analytics.run", user_id=admin.id, entity_type="pipeline_run", entity_id=summary.run_id
    )
    return {
        "pipeline_run_id": str(summary.run_id),
        "quarter": summary.quarter,
        "demand_rows": summary.demand_rows,
        "skill_rows": summary.skill_rows,
        "supply_rows": summary.supply_rows,
        "mismatch_rows": summary.mismatch_rows,
    }
