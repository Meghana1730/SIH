"""Audit log: an append-only record of important security and data events.

Never put secrets in `details` (no passwords, tokens or API keys). Email addresses of failed
logins are stored only as a short hash, so attempts can be correlated without keeping them.
"""

import hashlib
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def email_fingerprint(email: str) -> str:
    return hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]


def record_audit(
    db: Session,
    action: str,
    *,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Write one audit entry and commit immediately, so it is kept even if the request fails
    afterwards (e.g. a refused login)."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            diff_json=details or {},
        )
    )
    db.commit()
