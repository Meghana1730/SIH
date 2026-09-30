"""Employers and industry signals: surveys, consultations, sector events and indicators."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    Provenance,
    Timestamps,
    UUIDPrimaryKey,
    between,
    check_in,
    json_array,
    quarter_format,
)
from app.models.enums import (
    EmployerSize,
    ExtractionMethod,
    GeographyLevel,
    InsightType,
    Language,
    MappingReviewStatus,
    ParticipantType,
    SectorEventType,
    SurveyChannel,
    Willingness,
)

if TYPE_CHECKING:
    from app.models.engagement import Pledge, ValidationVote
    from app.models.geography import District
    from app.models.taxonomy import Sector, Skill


class Employer(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """A business that hires. No personal contact details are stored here (privacy)."""

    __tablename__ = "employer"

    code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(250))
    sector_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sector.id", ondelete="SET NULL"), index=True
    )
    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("district.id"), index=True)
    size: Mapped[str] = mapped_column(
        String(16), default=EmployerSize.UNKNOWN.value, server_default=EmployerSize.UNKNOWN.value
    )
    # Self-reported MSME registration (no registration number is stored).
    is_msme_registered: Mapped[bool | None]

    district: Mapped[District] = relationship(back_populates="employers")
    sector: Mapped[Sector | None] = relationship()
    survey_responses: Mapped[list[EmployerSurveyResponse]] = relationship(back_populates="employer")
    votes: Mapped[list[ValidationVote]] = relationship(back_populates="employer")
    pledges: Mapped[list[Pledge]] = relationship(back_populates="employer")

    __table_args__ = (check_in("size", "size", EmployerSize),)


class EmployerSurveyResponse(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """One answered employer survey (web form, Telegram, WhatsApp or phone).

    roles_json  : list like [{"role_id": "...", "role_text": "EV technician",
                             "count": 5, "timeframe_months": 12}]
    skills_json : list like [{"skill_id": "...", "text": "high-voltage safety"}]
    """

    __tablename__ = "employer_survey_response"

    employer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employer.id", ondelete="SET NULL"), index=True
    )
    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("district.id"), index=True)
    business_type: Mapped[str | None] = mapped_column(String(60))
    business_size: Mapped[str | None] = mapped_column(String(16))
    channel: Mapped[str] = mapped_column(String(16))
    language: Mapped[str] = mapped_column(String(8), default=Language.EN.value, server_default="en")
    consent_given: Mapped[bool]
    submitted_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    roles_json: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    skills_json: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    hardest_skills_text: Mapped[str | None] = mapped_column(Text)
    apprenticeship_willingness: Mapped[str | None] = mapped_column(String(8))
    apprentices_possible: Mapped[int | None]
    recontact_consent: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    employer: Mapped[Employer | None] = relationship(back_populates="survey_responses")
    district: Mapped[District] = relationship()

    __table_args__ = (
        # No consent, no record (docs/DATA_COLLECTION_PLAN.md §7.1).
        CheckConstraint("consent_given", name="consent_required"),
        check_in("business_size", "business_size", EmployerSize),
        check_in("channel", "channel", SurveyChannel),
        check_in("language", "language", Language),
        check_in("apprenticeship_willingness", "apprenticeship_willingness", Willingness),
        CheckConstraint("apprentices_possible >= 0", name="apprentices_not_negative"),
        json_array("roles_json_is_array", "roles_json"),
        json_array("skills_json_is_array", "skills_json"),
    )


class Consultation(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """Notes from an interview with an employer, instructor or association (anonymised)."""

    __tablename__ = "consultation"

    title: Mapped[str] = mapped_column(String(250))
    held_on: Mapped[date]
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("district.id", ondelete="SET NULL"), index=True
    )
    sector_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sector.id", ondelete="SET NULL"), index=True
    )
    participant_type: Mapped[str] = mapped_column(String(16))
    notes: Mapped[str] = mapped_column(Text)
    consent_to_quote: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    district: Mapped[District | None] = relationship()
    sector: Mapped[Sector | None] = relationship()
    insights: Mapped[list[ConsultationInsight]] = relationship(
        back_populates="consultation", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (check_in("participant_type", "participant_type", ParticipantType),)


class ConsultationInsight(UUIDPrimaryKey, Timestamps, Base):
    """One finding from a consultation, optionally with an approved quote."""

    __tablename__ = "consultation_insight"

    consultation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation.id", ondelete="CASCADE"), index=True
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("skill.id", ondelete="SET NULL"), index=True
    )
    insight_type: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(Text)
    quote: Mapped[str | None] = mapped_column(Text)
    quote_approved: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    extracted_by: Mapped[str] = mapped_column(
        String(16),
        default=ExtractionMethod.HUMAN.value,
        server_default=ExtractionMethod.HUMAN.value,
    )
    review_status: Mapped[str] = mapped_column(
        String(16),
        default=MappingReviewStatus.PENDING.value,
        server_default=MappingReviewStatus.PENDING.value,
    )
    # TRUE when the consultation is synthetic (the writer copies it from the consultation).
    is_synthetic: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    consultation: Mapped[Consultation] = relationship(back_populates="insights")
    skill: Mapped[Skill | None] = relationship()

    __table_args__ = (
        check_in("insight_type", "insight_type", InsightType),
        check_in("extracted_by", "extracted_by", ExtractionMethod),
        check_in("review_status", "review_status", MappingReviewStatus),
        CheckConstraint("NOT quote_approved OR quote IS NOT NULL", name="approved_quote_present"),
    )


class SectorEvent(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """Something in the economy that changes future demand (new plant, closure, policy...).
    Events created in the demo are `is_simulated` and must also be `is_synthetic`."""

    __tablename__ = "sector_event"

    sector_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sector.id"), index=True)
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("district.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    expected_jobs: Mapped[int | None]
    announced_on: Mapped[date]
    announced_quarter: Mapped[str] = mapped_column(String(7))
    realization_factor: Mapped[float | None]  # share of announced jobs expected to appear, 0..1
    citation_url: Mapped[str | None] = mapped_column(Text)
    is_simulated: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    sector: Mapped[Sector] = relationship()
    district: Mapped[District | None] = relationship()

    __table_args__ = (
        check_in("event_type", "event_type", SectorEventType),
        quarter_format("announced_quarter_format", "announced_quarter"),
        CheckConstraint("expected_jobs >= 0", name="expected_jobs_not_negative"),
        between("realization_factor_range", "realization_factor", 0, 1),
        CheckConstraint("NOT is_simulated OR is_synthetic", name="simulated_is_synthetic"),
        Index("ix_sector_event_district_quarter", "district_id", "announced_quarter"),
    )


class SectorIndicator(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """A published number about sector growth, e.g. EV registrations per RTO per month.
    `period` is flexible: '2026Q3', '2026-08' or '2025'."""

    __tablename__ = "sector_indicator"

    sector_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sector.id", ondelete="SET NULL"), index=True
    )
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("district.id", ondelete="SET NULL"), index=True
    )
    geography_level: Mapped[str] = mapped_column(String(16))
    geography_name: Mapped[str] = mapped_column(String(120))
    indicator: Mapped[str] = mapped_column(String(80))
    period: Mapped[str] = mapped_column(String(16))
    value: Mapped[float]
    unit: Mapped[str | None] = mapped_column(String(40))

    sector: Mapped[Sector | None] = relationship()
    district: Mapped[District | None] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "indicator",
            "geography_level",
            "geography_name",
            "period",
            name="uq_sector_indicator_natural_key",  # explicit: auto name > 63 chars
        ),
        check_in("geography_level", "geography_level", GeographyLevel),
        CheckConstraint(
            "geography_level <> 'DISTRICT' OR district_id IS NOT NULL",
            name="district_level_needs_district",
        ),
    )
