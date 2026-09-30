"""Demand signals from job postings, and external technology-trend signals."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    CreatedAt,
    Provenance,
    Timestamps,
    UUIDPrimaryKey,
    between,
    check_in,
    json_object,
    quarter_format,
)
from app.models.enums import (
    EvidenceKind,
    ExtractionMethod,
    ExtractionStatus,
    GeographyLevel,
    Language,
    MatchDecision,
    Proficiency,
    SalaryPeriod,
)

if TYPE_CHECKING:
    from app.models.employers import Employer
    from app.models.geography import District
    from app.models.taxonomy import JobRole, Sector, Skill


class JobPosting(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """A job advertisement. Phone numbers / e-mails must be removed before storing."""

    __tablename__ = "job_posting"

    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    employer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employer.id", ondelete="SET NULL"), index=True
    )
    employer_name_raw: Mapped[str | None] = mapped_column(Text)
    # NULL until the raw location is mapped to a district (unmapped ones go to review).
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("district.id", ondelete="SET NULL")
    )
    # Sector given by the source (CSV `sector` column); NULL if unknown.
    sector_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sector.id", ondelete="SET NULL"), index=True
    )
    location_raw: Mapped[str | None] = mapped_column(Text)
    posted_on: Mapped[date] = mapped_column(index=True)
    quarter: Mapped[str] = mapped_column(String(7))  # derived from posted_on, e.g. "2026Q3"
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_period: Mapped[str | None] = mapped_column(String(8))
    experience_min_years: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    experience_max_years: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    language: Mapped[str] = mapped_column(String(8), default=Language.EN.value, server_default="en")
    # Hash of normalised title + employer + district + week; stops duplicate postings.
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True)
    extraction_status: Mapped[str] = mapped_column(
        String(16),
        default=ExtractionStatus.PENDING.value,
        server_default=ExtractionStatus.PENDING.value,
    )
    # Last run of the job pipeline on this posting (and its error, if it FAILED).
    processed_at: Mapped[datetime | None]
    extraction_error: Mapped[str | None] = mapped_column(Text)

    employer: Mapped[Employer | None] = relationship()
    district: Mapped[District | None] = relationship()
    sector: Mapped[Sector | None] = relationship()
    skill_links: Mapped[list[PostingSkill]] = relationship(
        back_populates="posting", cascade="all, delete-orphan", passive_deletes=True
    )
    role_links: Mapped[list[PostingRole]] = relationship(
        back_populates="posting", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        quarter_format("quarter_format", "quarter"),
        check_in("salary_period", "salary_period", SalaryPeriod),
        check_in("language", "language", Language),
        check_in("extraction_status", "extraction_status", ExtractionStatus),
        CheckConstraint("salary_min >= 0", name="salary_min_not_negative"),
        CheckConstraint("salary_min <= salary_max", name="salary_min_le_max"),
        CheckConstraint("experience_min_years >= 0", name="experience_not_negative"),
        CheckConstraint(
            "experience_min_years <= experience_max_years", name="experience_min_le_max"
        ),
        Index("ix_job_posting_district_quarter", "district_id", "quarter"),
    )


class PostingSkill(CreatedAt, Base):
    """A skill a posting asks for, with its evidence (docs/06-job-intelligence.md).

    evidence_kind : OBSERVED (quoted from the ad), INFERRED (implied by the matched role),
                    SYNTHETIC (synthetic-generator ground truth)
    decision      : accept, or review (a human should confirm)
    proficiency   : what the ad asks for (basic/intermediate/advanced/unknown), not certified
    matched_text  : the words of the ad that matched; evidence_text: the sentence around them
    evidence_json : details (field, character span, vocabulary term, alternatives, LLM
                    provenance ...)
    """

    __tablename__ = "posting_skill"

    posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_posting.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    confidence: Mapped[float]
    method: Mapped[str] = mapped_column(String(16))
    band: Mapped[int | None] = mapped_column(SmallInteger)
    matched_text: Mapped[str | None] = mapped_column(Text)
    evidence_kind: Mapped[str] = mapped_column(
        String(12), default=EvidenceKind.OBSERVED.value, server_default=EvidenceKind.OBSERVED.value
    )
    decision: Mapped[str] = mapped_column(
        String(8), default=MatchDecision.ACCEPT.value, server_default=MatchDecision.ACCEPT.value
    )
    proficiency: Mapped[str] = mapped_column(
        String(16), default=Proficiency.UNKNOWN.value, server_default=Proficiency.UNKNOWN.value
    )
    evidence_text: Mapped[str | None] = mapped_column(Text)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    # TRUE when the posting is synthetic (the writer copies it from the posting).
    is_synthetic: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    posting: Mapped[JobPosting] = relationship(back_populates="skill_links")
    skill: Mapped[Skill] = relationship()

    __table_args__ = (
        between("confidence_range", "confidence", 0, 1),
        check_in("method", "method", ExtractionMethod),
        between("band_range", "band", 1, 4),
        check_in("evidence_kind", "evidence_kind", EvidenceKind),
        check_in("decision", "decision", MatchDecision),
        check_in("proficiency", "proficiency", Proficiency),
        json_object("evidence_json_is_object", "evidence_json"),
    )


class PostingRole(CreatedAt, Base):
    """The job role a posting was classified as, with its evidence (see PostingSkill)."""

    __tablename__ = "posting_role"

    posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_posting.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_role.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    confidence: Mapped[float]
    method: Mapped[str] = mapped_column(String(16))
    evidence_kind: Mapped[str] = mapped_column(
        String(12), default=EvidenceKind.OBSERVED.value, server_default=EvidenceKind.OBSERVED.value
    )
    decision: Mapped[str] = mapped_column(
        String(8), default=MatchDecision.ACCEPT.value, server_default=MatchDecision.ACCEPT.value
    )
    evidence_text: Mapped[str | None] = mapped_column(Text)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    # TRUE when the posting is synthetic (the writer copies it from the posting).
    is_synthetic: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    posting: Mapped[JobPosting] = relationship(back_populates="role_links")
    role: Mapped[JobRole] = relationship()

    __table_args__ = (
        between("confidence_range", "confidence", 0, 1),
        check_in("method", "method", ExtractionMethod),
        check_in("evidence_kind", "evidence_kind", EvidenceKind),
        check_in("decision", "decision", MatchDecision),
        json_object("evidence_json_is_object", "evidence_json"),
    )


class TrendSignal(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """An external technology-trend number for a skill (e.g. national mentions growth)."""

    __tablename__ = "trend_signal"

    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill.id", ondelete="CASCADE"), index=True
    )
    signal_name: Mapped[str] = mapped_column(String(80))
    geography_level: Mapped[str] = mapped_column(
        String(16),
        default=GeographyLevel.NATIONAL.value,
        server_default=GeographyLevel.NATIONAL.value,
    )
    period: Mapped[str] = mapped_column(String(16))
    value: Mapped[float]

    skill: Mapped[Skill] = relationship()

    __table_args__ = (
        UniqueConstraint("skill_id", "signal_name", "geography_level", "period"),
        check_in("geography_level", "geography_level", GeographyLevel),
    )
