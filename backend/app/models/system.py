"""Platform tables: users, audit log, ingestion and pipeline runs, review queue,
versioned scoring configuration and the LLM response cache."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    CreatedAt,
    Timestamps,
    UUIDPrimaryKey,
    between,
    check_in,
    json_array,
    json_object,
    quarter_format,
)
from app.models.enums import Language, ReviewItemStatus, ReviewKind, RunStatus, UserRole

if TYPE_CHECKING:
    from app.models.candidates import Candidate
    from app.models.employers import Employer
    from app.models.geography import District
    from app.models.taxonomy import Skill
    from app.models.training import Institute


class AppUser(UUIDPrimaryKey, Timestamps, Base):
    """A login. Staff roles need their scope (see CHECK rules below).

    Scope per role: state_officer -> state_name, district_officer -> district_id,
    institute_admin -> institute_id, employer -> employer_id, candidate -> candidate_id
    (optional: the candidate's own profile). admin and ssc_reviewer have no scope field.
    `password_hash` is always an argon2id hash; the database refuses anything else.
    """

    __tablename__ = "app_user"

    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    state_name: Mapped[str | None] = mapped_column(String(100))
    district_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("district.id"), index=True)
    institute_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("institute.id"), index=True)
    employer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employer.id"), index=True)
    # A candidate login may be linked to exactly one candidate profile.
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("candidate.id", ondelete="SET NULL"), unique=True
    )
    language: Mapped[str] = mapped_column(String(8), default=Language.EN.value, server_default="en")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    is_demo: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    last_login_at: Mapped[datetime | None]

    district: Mapped[District | None] = relationship()
    institute: Mapped[Institute | None] = relationship()
    employer: Mapped[Employer | None] = relationship()
    candidate: Mapped[Candidate | None] = relationship()

    __table_args__ = (
        check_in("role", "role", UserRole),
        check_in("language", "language", Language),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint(
            "(role <> 'state_officer' OR state_name IS NOT NULL) AND "
            "(role <> 'district_officer' OR district_id IS NOT NULL) AND "
            "(role <> 'institute_admin' OR institute_id IS NOT NULL) AND "
            "(role <> 'employer' OR employer_id IS NOT NULL)",
            name="role_has_scope",
        ),
        # A user carries only the scope of its own role (no district on an employer, etc.).
        CheckConstraint(
            "(state_name IS NULL OR role = 'state_officer') AND "
            "(district_id IS NULL OR role = 'district_officer') AND "
            "(institute_id IS NULL OR role = 'institute_admin') AND "
            "(employer_id IS NULL OR role = 'employer') AND "
            "(candidate_id IS NULL OR role = 'candidate')",
            name="scope_matches_role",
        ),
        # Never plain text: only argon2id hashes are accepted.
        CheckConstraint("password_hash LIKE '$argon2id$%'", name="password_is_argon2_hash"),
    )


class AuditLog(UUIDPrimaryKey, CreatedAt, Base):
    """Append-only record of who changed what (status changes, votes, pledges, resets...)."""

    __tablename__ = "audit_log"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))  # text: not every key is a UUID
    diff_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    request_id: Mapped[str | None] = mapped_column(String(64))

    user: Mapped[AppUser | None] = relationship()

    __table_args__ = (
        json_object("diff_json_is_object", "diff_json"),
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_created_at", "created_at"),
    )


class IngestionRun(UUIDPrimaryKey, Timestamps, Base):
    """One load of a data file. Every data record points back to the run that loaded it."""

    __tablename__ = "ingestion_run"

    source: Mapped[str] = mapped_column(String(64), index=True)
    file_name: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16), default=RunStatus.RUNNING.value, server_default=RunStatus.RUNNING.value
    )
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]
    rows_loaded: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    rows_rejected: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    # [{"row": 12, "reason": "unknown district code"}, ...]
    errors_json: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )

    __table_args__ = (
        check_in("status", "status", RunStatus),
        CheckConstraint("rows_loaded >= 0 AND rows_rejected >= 0", name="counts_not_negative"),
        CheckConstraint("finished_at >= started_at", name="finished_after_started"),
        json_array("errors_json_is_array", "errors_json"),
    )


class ScoringConfigVersion(UUIDPrimaryKey, Timestamps, Base):
    """A saved copy of config/scoring.yaml. Exactly one version can be active, and only
    after it has been approved."""

    __tablename__ = "scoring_config_version"

    version: Mapped[str] = mapped_column(String(32), unique=True)
    config_sha256: Mapped[str] = mapped_column(String(64))
    config_yaml: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None]

    created_by: Mapped[AppUser | None] = relationship(foreign_keys=[created_by_id])
    approved_by: Mapped[AppUser | None] = relationship(foreign_keys=[approved_by_id])

    __table_args__ = (
        CheckConstraint("config_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint("NOT is_active OR approved_at IS NOT NULL", name="active_must_be_approved"),
        Index(
            "uq_scoring_config_version_one_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )


class PipelineRun(UUIDPrimaryKey, Timestamps, Base):
    """One run of the analytics pipeline. All computed results point to their run; only one
    successful run is `is_current` at a time (the one the app shows)."""

    __tablename__ = "pipeline_run"

    status: Mapped[str] = mapped_column(
        String(16), default=RunStatus.QUEUED.value, server_default=RunStatus.QUEUED.value
    )
    quarter: Mapped[str] = mapped_column(String(7))
    is_current: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    config_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scoring_config_version.id"), index=True
    )
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    step_timings_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    config_version: Mapped[ScoringConfigVersion] = relationship()
    triggered_by: Mapped[AppUser | None] = relationship()

    __table_args__ = (
        check_in("status", "status", RunStatus),
        quarter_format("quarter_format", "quarter"),
        CheckConstraint("NOT is_current OR status = 'SUCCEEDED'", name="current_must_succeed"),
        CheckConstraint("finished_at >= started_at", name="finished_after_started"),
        json_object("step_timings_is_object", "step_timings_json"),
        Index(
            "uq_pipeline_run_one_current",
            "is_current",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )


class ReviewItem(UUIDPrimaryKey, Timestamps, Base):
    """Something a human must check: an uncertain skill match, an unknown place name, ..."""

    __tablename__ = "review_item"

    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        String(16), default=ReviewItemStatus.OPEN.value, server_default=ReviewItemStatus.OPEN.value
    )
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    confidence: Mapped[float | None]
    suggested_skill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("skill.id", ondelete="SET NULL")
    )
    source_table: Mapped[str | None] = mapped_column(String(64))
    source_record_id: Mapped[str | None] = mapped_column(String(64))
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None]
    resolution_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )

    suggested_skill: Mapped[Skill | None] = relationship()
    reviewer: Mapped[AppUser | None] = relationship()

    __table_args__ = (
        check_in("kind", "kind", ReviewKind),
        check_in("status", "status", ReviewItemStatus),
        between("confidence_range", "confidence", 0, 1),
        json_object("payload_json_is_object", "payload_json"),
        json_object("resolution_json_is_object", "resolution_json"),
        CheckConstraint(
            "status = 'OPEN' OR resolved_at IS NOT NULL", name="resolved_has_timestamp"
        ),
        Index("ix_review_item_kind_status", "kind", "status"),
    )


class LlmCache(CreatedAt, Base):
    """Cached LLM answers, so repeated requests (and the demo) give identical results.
    The key is a SHA-256 of provider + model + task + prompt version + input."""

    __tablename__ = "llm_cache"

    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(120))
    task: Mapped[str] = mapped_column(String(64), index=True)
    prompt_version: Mapped[str] = mapped_column(String(32))
    response_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    last_used_at: Mapped[datetime | None]

    __table_args__ = (CheckConstraint("cache_key ~ '^[0-9a-f]{64}$'", name="cache_key_hex"),)
