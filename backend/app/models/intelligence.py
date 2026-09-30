"""Results computed by the pipeline (demand, supply, mismatch, forecast, course health) and
recommendations. Engines are NOT implemented yet; these tables only store their outputs.

Every computed row belongs to one `pipeline_run`. A new run writes new rows; the app reads the
run marked `is_current` (docs/04-architecture.md §5.5). Recommendations are different: they
keep a stable identity (fingerprint) across runs so employer votes and pledges are never lost.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.models.base import (
    Base,
    CreatedAt,
    Timestamps,
    UUIDPrimaryKey,
    academic_year_format,
    between,
    check_in,
    json_array,
    json_object,
    quarter_format,
)
from app.models.enums import (
    Confidence,
    CourseFlag,
    DecisionOwner,
    MismatchStatus,
    Priority,
    RecommendationStatus,
    RecommendationType,
    TrendStatus,
)

if TYPE_CHECKING:
    from app.models.engagement import Pledge, ValidationVote
    from app.models.geography import District
    from app.models.system import AppUser, PipelineRun
    from app.models.taxonomy import JobRole, Skill
    from app.models.training import CourseOffering, Institute


class DerivedResult(UUIDPrimaryKey, CreatedAt):
    """Columns shared by every computed result (explainability, docs/04-architecture.md §10).

    components_json : how the number was built, e.g. [{"name": "postings", "weight": 0.5, ...}]
    evidence_json   : facts behind it,
                      e.g. [{"type": "POSTING_TREND", "summary_key": ..., "value": 212}]
    synthetic_share : 0..1, share of input records that were synthetic ("demo data" badge if > 0)
    """

    @declared_attr
    def pipeline_run_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805 (SQLAlchemy pattern)
        return mapped_column(ForeignKey("pipeline_run.id", ondelete="CASCADE"), index=True)

    confidence: Mapped[str] = mapped_column(String(8))
    synthetic_share: Mapped[float] = mapped_column(default=0.0, server_default=text("0"))
    components_json: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    evidence_json: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )


def derived_rules() -> tuple:
    """CHECK constraints every DerivedResult table gets (new objects per table)."""
    return (
        check_in("confidence", "confidence", Confidence),
        between("synthetic_share_range", "synthetic_share", 0, 1),
        json_array("components_json_is_array", "components_json"),
        json_array("evidence_json_is_array", "evidence_json"),
    )


class DemandScore(DerivedResult, Base):
    """Demand index (0-100) for EITHER a job role OR a skill, in a district and quarter."""

    __tablename__ = "demand_score"

    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("district.id", ondelete="CASCADE"))
    quarter: Mapped[str] = mapped_column(String(7))
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_role.id", ondelete="CASCADE"), index=True
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("skill.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[float]
    estimated_openings: Mapped[float | None]  # role rows only; an estimate (PRD §7.2)
    mention_count: Mapped[int | None]  # skill rows: postings mentioning the skill
    trend_status: Mapped[str | None] = mapped_column(String(16))  # skill rows only

    pipeline_run: Mapped[PipelineRun] = relationship()
    district: Mapped[District] = relationship()
    role: Mapped[JobRole | None] = relationship()
    skill: Mapped[Skill | None] = relationship()

    __table_args__ = (
        *derived_rules(),
        quarter_format("quarter_format", "quarter"),
        between("score_range", "score", 0, 100),
        CheckConstraint("estimated_openings >= 0", name="openings_not_negative"),
        CheckConstraint("mention_count >= 0", name="mentions_not_negative"),
        check_in("trend_status", "trend_status", TrendStatus),
        # Exactly one of role_id / skill_id is set.
        CheckConstraint("num_nonnulls(role_id, skill_id) = 1", name="role_xor_skill"),
        CheckConstraint("trend_status IS NULL OR skill_id IS NOT NULL", name="trend_for_skills"),
        Index("ix_demand_score_run_district_quarter", "pipeline_run_id", "district_id", "quarter"),
        Index(
            "uq_demand_score_role_row",
            "pipeline_run_id",
            "district_id",
            "quarter",
            "role_id",
            unique=True,
            postgresql_where=text("role_id IS NOT NULL"),
        ),
        Index(
            "uq_demand_score_skill_row",
            "pipeline_run_id",
            "district_id",
            "quarter",
            "skill_id",
            unique=True,
            postgresql_where=text("skill_id IS NOT NULL"),
        ),
    )


class SupplyEstimate(DerivedResult, Base):
    """Trained people per year for a role in a district (components list contributing offerings)."""

    __tablename__ = "supply_estimate"

    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("district.id", ondelete="CASCADE"))
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_role.id", ondelete="CASCADE"), index=True
    )
    academic_year: Mapped[str] = mapped_column(String(7))
    trained_output: Mapped[float]

    pipeline_run: Mapped[PipelineRun] = relationship()
    district: Mapped[District] = relationship()
    role: Mapped[JobRole] = relationship()

    __table_args__ = (
        *derived_rules(),
        UniqueConstraint(
            "pipeline_run_id",
            "district_id",
            "role_id",
            "academic_year",
            name="uq_supply_estimate_run_district_role_year",  # explicit: auto name > 63 chars
        ),
        academic_year_format("academic_year_format", "academic_year"),
        CheckConstraint("trained_output >= 0", name="output_not_negative"),
    )


class Mismatch(DerivedResult, Base):
    """Supply vs estimated openings for a role in a district (PRD §7.4)."""

    __tablename__ = "mismatch"

    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("district.id", ondelete="CASCADE"))
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_role.id", ondelete="CASCADE"), index=True
    )
    quarter: Mapped[str] = mapped_column(String(7))
    supply: Mapped[float]
    openings: Mapped[float]
    ratio: Mapped[float | None]  # supply / openings; NULL when openings = 0
    status: Mapped[str] = mapped_column(String(20))

    pipeline_run: Mapped[PipelineRun] = relationship()
    district: Mapped[District] = relationship()
    role: Mapped[JobRole] = relationship()

    __table_args__ = (
        *derived_rules(),
        UniqueConstraint("pipeline_run_id", "district_id", "role_id", "quarter"),
        quarter_format("quarter_format", "quarter"),
        check_in("status", "status", MismatchStatus),
        CheckConstraint("supply >= 0 AND openings >= 0", name="amounts_not_negative"),
        CheckConstraint("ratio >= 0", name="ratio_not_negative"),
        CheckConstraint(
            "ratio IS NOT NULL OR status = 'INSUFFICIENT_DATA'",
            name="missing_ratio_is_insufficient",
        ),
    )


class Forecast(DerivedResult, Base):
    """Indicative future openings for a role in a district, with a range (PRD §7.6)."""

    __tablename__ = "forecast"

    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("district.id", ondelete="CASCADE"))
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_role.id", ondelete="CASCADE"), index=True
    )
    target_quarter: Mapped[str] = mapped_column(String(7))
    horizon_quarters: Mapped[int] = mapped_column(SmallInteger)
    value: Mapped[float]
    lower_bound: Mapped[float]
    upper_bound: Mapped[float]
    method: Mapped[str] = mapped_column(String(40))
    includes_event_uplift: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    pipeline_run: Mapped[PipelineRun] = relationship()
    district: Mapped[District] = relationship()
    role: Mapped[JobRole] = relationship()

    __table_args__ = (
        *derived_rules(),
        UniqueConstraint("pipeline_run_id", "district_id", "role_id", "target_quarter"),
        quarter_format("target_quarter_format", "target_quarter"),
        between("horizon_range", "horizon_quarters", 1, 12),
        CheckConstraint(
            "lower_bound <= value AND value <= upper_bound", name="value_within_bounds"
        ),
        CheckConstraint("lower_bound >= 0", name="lower_not_negative"),
    )


class CourseHealth(DerivedResult, Base):
    """Health score (0-100) and skill coverage (0-1) of a course offering, with flags (PRD §7.7)."""

    __tablename__ = "course_health"

    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_offering.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[float]
    coverage: Mapped[float]
    flags: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), default=list, server_default=text("'{}'")
    )

    pipeline_run: Mapped[PipelineRun] = relationship()
    course_offering: Mapped[CourseOffering] = relationship()

    __table_args__ = (
        *derived_rules(),
        UniqueConstraint("pipeline_run_id", "course_offering_id"),
        between("score_range", "score", 0, 100),
        between("coverage_range", "coverage", 0, 1),
        CheckConstraint(
            "flags <@ ARRAY[{}]::varchar[]".format(", ".join(f"'{f}'" for f in CourseFlag)),
            name="flags_known",
        ),
    )


class Recommendation(UUIDPrimaryKey, Timestamps, Base):
    """A proposed action with evidence (PRD F11). Persistent across pipeline runs.

    payload_json  : details, e.g. draft module outline, equipment list, trainer (ToT) needs
    evidence_json : at least 2 evidence items, unless `limited_evidence` (then confidence LOW)
    """

    __tablename__ = "recommendation"

    # Stable identity: hash of (type, target, skill, district). Same situation -> same row.
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    rec_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        String(20),
        default=RecommendationStatus.DRAFT.value,
        server_default=RecommendationStatus.DRAFT.value,
    )
    priority: Mapped[str] = mapped_column(String(8))
    confidence: Mapped[str] = mapped_column(String(8))
    decision_owner: Mapped[str | None] = mapped_column(String(20))

    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("district.id"))
    institute_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institute.id", ondelete="SET NULL"), index=True
    )
    course_offering_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("course_offering.id", ondelete="SET NULL"), index=True
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_role.id", ondelete="SET NULL"), index=True
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("skill.id", ondelete="SET NULL"), index=True
    )

    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    evidence_json: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    limited_evidence: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    synthetic_share: Mapped[float] = mapped_column(default=0.0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    first_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_run.id", ondelete="SET NULL")
    )
    last_seen_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_run.id", ondelete="SET NULL")
    )
    status_changed_at: Mapped[datetime | None]
    status_changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )

    district: Mapped[District] = relationship()
    institute: Mapped[Institute | None] = relationship()
    course_offering: Mapped[CourseOffering | None] = relationship()
    role: Mapped[JobRole | None] = relationship()
    skill: Mapped[Skill | None] = relationship()
    first_run: Mapped[PipelineRun | None] = relationship(foreign_keys=[first_run_id])
    last_seen_run: Mapped[PipelineRun | None] = relationship(foreign_keys=[last_seen_run_id])
    status_changed_by: Mapped[AppUser | None] = relationship()
    votes: Mapped[list[ValidationVote]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan", passive_deletes=True
    )
    pledges: Mapped[list[Pledge]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        check_in("rec_type", "rec_type", RecommendationType),
        check_in("status", "status", RecommendationStatus),
        check_in("priority", "priority", Priority),
        check_in("confidence", "confidence", Confidence),
        check_in("decision_owner", "decision_owner", DecisionOwner),
        between("synthetic_share_range", "synthetic_share", 0, 1),
        json_object("payload_json_is_object", "payload_json"),
        json_array("evidence_json_is_array", "evidence_json"),
        # Explainability rule EXP-2: >= 2 evidence items, or openly marked as limited.
        CheckConstraint(
            "limited_evidence OR jsonb_array_length(evidence_json) >= 2",
            name="evidence_required",
        ),
        CheckConstraint(
            "NOT limited_evidence OR confidence = 'LOW'", name="limited_evidence_low_confidence"
        ),
        Index("ix_recommendation_district_status", "district_id", "status"),
    )
