"""Reusable FastAPI dependencies: database session, current user, role checks, scoped lookups.

@router.get("/admin/users")
def list_users(user: Annotated[AppUser, Depends(require_roles(UserRole.ADMIN))]): ...
"""

import uuid
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import TokenError, decode_access_token
from app.models import AppUser
from app.models.enums import UserRole
from app.services.audit import record_audit

DbSession = Annotated[Session, Depends(get_db)]

# Reads "Authorization: Bearer <token>". Adds the "Authorize" button to /docs.
bearer_scheme = HTTPBearer(
    auto_error=False, description="Paste the access_token returned by POST /api/v1/auth/login"
)


def error(status_code: int, code: str, message: str, **headers: str) -> HTTPException:
    return HTTPException(status_code, detail={"code": code, "message": message}, headers=headers)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> AppUser | None:
    """The logged-in user, or None if no token was sent. A bad token is always an error."""
    if credentials is None:
        return None
    invalid = error(
        401,
        "INVALID_TOKEN",
        "The login token is invalid or has expired. Log in again.",
        **{"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(str(claims["sub"]))
    except (TokenError, ValueError, KeyError):
        raise invalid from None
    user = db.get(AppUser, user_id)
    if user is None or not user.is_active:
        raise invalid
    return user


def get_current_user(
    user: Annotated[AppUser | None, Depends(get_optional_user)],
) -> AppUser:
    if user is None:
        raise error(
            401,
            "NOT_AUTHENTICATED",
            "Log in first and send the header 'Authorization: Bearer <token>'.",
            **{"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[AppUser, Depends(get_current_user)]
OptionalUser = Annotated[AppUser | None, Depends(get_optional_user)]


def require_roles(*roles: UserRole) -> Callable[..., AppUser]:
    """Dependency: the current user must have one of `roles`, otherwise 403 (and audit)."""
    allowed = {role.value for role in roles}

    def check_role(user: CurrentUser, db: DbSession, request: Request) -> AppUser:
        if user.role not in allowed:
            record_audit(
                db,
                "auth.access_denied",
                user_id=user.id,
                details={
                    "reason": "role",
                    "role": user.role,
                    "path": request.url.path,
                    "allowed_roles": sorted(allowed),
                },
            )
            raise error(403, "FORBIDDEN_ROLE", f"The '{user.role}' role cannot use this endpoint.")
        return user

    return check_role


def get_in_scope(
    db: Session,
    user: AppUser,
    model: Any,
    record_id: uuid.UUID,
    scope: ColumnElement[bool],
) -> Any:
    """Load one record: 404 if it does not exist, 403 (and audit) if it is outside the user's
    scope (another district, institute, employer or candidate)."""
    record = db.get(model, record_id)
    if record is None:
        raise error(404, "NOT_FOUND", f"No {model.__tablename__} with id {record_id}.")
    if db.scalar(select(model.id).where(model.id == record_id, scope)) is None:
        record_audit(
            db,
            "auth.access_denied",
            user_id=user.id,
            entity_type=model.__tablename__,
            entity_id=record_id,
            details={"reason": "scope", "role": user.role},
        )
        raise error(
            403, "FORBIDDEN_SCOPE", f"This {model.__tablename__} is outside your area of access."
        )
    return record
