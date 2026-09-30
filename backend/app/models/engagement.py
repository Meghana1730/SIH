"""Human decisions: employer validation votes, apprenticeship/hiring pledges, district plans."""

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
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    Timestamps,
    UUIDPrimaryKey,
    between,
    check_in,
    json_object,
    quarter_format,
)
from app.models.enums import PlanStatus, PledgeType, VoteChoice

if TYPE_CHECKING:
    from app.models.employers import Employer
    from app.models.geography import District
    from app.models.intelligence import Recommendation
    from app.models.system import AppUser, PipelineRun


class ValidationVote(UUIDPrimaryKey, Timestamps, Base):
    """An employer's verdict on a recommendation. One vote per employer (it can be changed)."""

    __tablename__ = "validation_vote"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendation.id", ondelete="CASCADE"), index=True
    )
    employer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employer.id", ondelete="CASCADE"), index=True
    )
    vote: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str | None] = mapped_column(Text)
    # Pre-seeded demo votes are synthetic.
    is_synthetic: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    recommendation: Mapped[Recommendation] = relationship(back_populates="votes")
    employer: Mapped[Employer] = relationship(back_populates="votes")

    __table_args__ = (
        UniqueConstraint("recommendation_id", "employer_id"),
        check_in("vote", "vote", VoteChoice),
    )


class Pledge(UUIDPrimaryKey, Timestamps, Base):
    """A non-binding promise to take apprentices or hire, if a recommendation is implemented."""

    __tablename__ = "pledge"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendation.id", ondelete="CASCADE"), index=True
    )
    employer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employer.id", ondelete="CASCADE"), index=True
    )
    pledge_type: Mapped[str] = mapped_column(String(16))
    count: Mapped[int]
    timeframe_months: Mapped[int] = mapped_column(SmallInteger)
    note: Mapped[str | None] = mapped_column(Text)
    is_synthetic: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    recommendation: Mapped[Recommendation] = relationship(back_populates="pledges")
    employer: Mapped[Employer] = relationship(back_populates="pledges")

    __table_args__ = (
        # One pledge per employer per type; changing it means updating the row.
        UniqueConstraint("recommendation_id", "employer_id", "pledge_type"),
        check_in("pledge_type", "pledge_type", PledgeType),
        between("count_range", "count", 1, 10000),
        between("timeframe_range", "timeframe_months", 1, 36),
    )


class DistrictPlan(UUIDPrimaryKey, Timestamps, Base):
    """A generated district action plan. `content_json` is a FROZEN copy of everything in the
    PDF (numbers, evidence, votes, pledges), so it can be regenerated identically later."""

    __tablename__ = "district_plan"

    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("district.id"))
    quarter: Mapped[str] = mapped_column(String(7))
    status: Mapped[str] = mapped_column(
        String(16), default=PlanStatus.DRAFT.value, server_default=PlanStatus.DRAFT.value
    )
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_run.id", ondelete="SET NULL"), index=True
    )
    content_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    pdf_path: Mapped[str | None] = mapped_column(Text)
    languages: Mapped[list[str]] = mapped_column(
        ARRAY(String(8)), default=lambda: ["en"], server_default=text("'{en}'")
    )
    synthetic_share: Mapped[float] = mapped_column(default=0.0, server_default=text("0"))
    generated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    generated_at: Mapped[datetime | None]

    district: Mapped[District] = relationship()
    pipeline_run: Mapped[PipelineRun | None] = relationship()
    generated_by: Mapped[AppUser | None] = relationship()

    __table_args__ = (
        quarter_format("quarter_format", "quarter"),
        check_in("status", "status", PlanStatus),
        json_object("content_json_is_object", "content_json"),
        CheckConstraint("languages <@ ARRAY['en', 'hi', 'mr']::varchar[]", name="languages_known"),
        between("synthetic_share_range", "synthetic_share", 0, 1),
        CheckConstraint(
            "status <> 'GENERATED' OR generated_at IS NOT NULL", name="generated_has_timestamp"
        ),
        Index("ix_district_plan_district_quarter", "district_id", "quarter"),
    )
