"""Small read-only views of reference and people records (used by the scoped endpoints)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _FromOrm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DistrictOut(_FromOrm):
    id: uuid.UUID
    code: str
    name: str
    state_name: str


class InstituteOut(_FromOrm):
    id: uuid.UUID
    code: str
    name: str
    institute_type: str
    district_id: uuid.UUID
    is_synthetic: bool


class EmployerOut(_FromOrm):
    id: uuid.UUID
    code: str
    name: str
    district_id: uuid.UUID
    size: str
    is_synthetic: bool


class CandidateOut(_FromOrm):
    """Pseudonymous: no names or contact details exist for candidates."""

    id: uuid.UUID
    pseudonym: str
    district_id: uuid.UUID
    education_level: str
    languages: list[str]
    is_synthetic: bool


class AuditEntryOut(_FromOrm):
    id: uuid.UUID
    created_at: datetime
    action: str
    user_id: uuid.UUID | None
    entity_type: str | None
    entity_id: str | None
    details: dict[str, Any] = Field(validation_alias="diff_json")
