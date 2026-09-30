"""Admin-only endpoints: user list and audit log."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps import DbSession, require_roles
from app.models import AppUser, AuditLog
from app.models.enums import UserRole
from app.schemas.auth import UserResponse
from app.schemas.directory import AuditEntryOut

router = APIRouter(prefix="/admin", tags=["admin"])

AdminUser = Annotated[AppUser, Depends(require_roles(UserRole.ADMIN))]


@router.get("/users", response_model=list[UserResponse])
def list_users(admin: AdminUser, db: DbSession) -> list[AppUser]:
    return list(db.scalars(select(AppUser).order_by(AppUser.created_at)))


@router.get("/audit-log", response_model=list[AuditEntryOut])
def audit_log(
    admin: AdminUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    action: str | None = None,
) -> list[AuditLog]:
    """Most recent audit entries first. Filter with e.g. ?action=auth.login.failure"""
    query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if action:
        query = query.where(AuditLog.action == action)
    return list(db.scalars(query))
