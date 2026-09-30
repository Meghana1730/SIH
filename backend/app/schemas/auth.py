"""Request/response models for /api/v1/auth. Passwords are SecretStr, so they are never
printed in logs or echoed back in error messages."""

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.models.enums import Language, UserRole

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    return value.strip().lower()


class RegisterRequest(BaseModel):
    """Public sign-up: only role "candidate", with consent=true and no scope fields.
    An admin (logged in) can create any role, with the scope that role needs."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=254, examples=["asha@example.com"])
    password: SecretStr = Field(examples=["a-long-passphrase"])
    display_name: str = Field(min_length=1, max_length=120)
    role: UserRole = UserRole.CANDIDATE
    language: Language = Language.EN
    # Agreement to the privacy notice. Required for public sign-up.
    consent: bool = False
    # Scope (only the field matching the role may be set; admins only):
    state_name: str | None = Field(default=None, max_length=100)
    district_id: uuid.UUID | None = None
    institute_id: uuid.UUID | None = None
    employer_id: uuid.UUID | None = None
    candidate_id: uuid.UUID | None = None

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        value = normalize_email(value)
        if not EMAIL_PATTERN.match(value):
            raise ValueError("not a valid email address")
        return value

    @field_validator("display_name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("display_name must not be empty")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=254)
    password: SecretStr

    @field_validator("email")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_email(value)


class UserResponse(BaseModel):
    """What the API shows about a user. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: UserRole
    language: Language
    state_name: str | None
    district_id: uuid.UUID | None
    institute_id: uuid.UUID | None
    employer_id: uuid.UUID | None
    candidate_id: uuid.UUID | None
    is_active: bool
    is_demo: bool
    last_login_at: datetime | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Seconds until the token expires")
    user: UserResponse
