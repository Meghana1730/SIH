"""Candidates, enrollments and outcomes. PROTOTYPE RULE: no real candidate data is stored,
so `candidate.is_synthetic` must be TRUE (enforced by a CHECK constraint)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    Provenance,
    Timestamps,
    UUIDPrimaryKey,
    between,
    check_in,
    json_object,
)
from app.models.enums import EducationLevel, EnrollmentStatus, PlacementType, SkillVerification

if TYPE_CHECKING:
    from app.models.employers import Employer
    from app.models.geography import District
    from app.models.taxonomy import JobRole, Skill
    from app.models.training import CourseOffering


class Candidate(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """A (synthetic) learner, identified only by a pseudonym such as "C-000123"."""

    __tablename__ = "candidate"

    pseudonym: Mapped[str] = mapped_column(String(40), unique=True)
    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("district.id"), index=True)
    education_level: Mapped[str] = mapped_column(String(16))
    languages: Mapped[list[str]] = mapped_column(
        ARRAY(String(8)), default=list, server_default=text("'{}'")
    )
    consent_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )

    district: Mapped[District] = relationship()
    skill_links: Mapped[list[CandidateSkill]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    enrollments: Mapped[list[Enrollment]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        # Privacy rule for the prototype (docs/03-prd.md SEC-1). Remove only with a privacy review.
        CheckConstraint("is_synthetic", name="synthetic_only"),
        check_in("education_level", "education_level", EducationLevel),
        json_object("consent_json_is_object", "consent_json"),
    )


class CandidateSkill(Timestamps, Provenance, Base):
    """A skill a candidate has, at a band, and how we know."""

    __tablename__ = "candidate_skill"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    band: Mapped[int] = mapped_column(SmallInteger)
    verified_by: Mapped[str] = mapped_column(
        String(16),
        default=SkillVerification.SELF.value,
        server_default=SkillVerification.SELF.value,
    )

    candidate: Mapped[Candidate] = relationship(back_populates="skill_links")
    skill: Mapped[Skill] = relationship()

    __table_args__ = (
        between("band_range", "band", 1, 4),
        check_in("verified_by", "verified_by", SkillVerification),
    )


class Enrollment(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """A candidate joining a course offering."""

    __tablename__ = "enrollment"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_offering.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default=EnrollmentStatus.ENROLLED.value,
        server_default=EnrollmentStatus.ENROLLED.value,
    )
    enrolled_on: Mapped[date]
    completed_on: Mapped[date | None]

    candidate: Mapped[Candidate] = relationship(back_populates="enrollments")
    course_offering: Mapped[CourseOffering] = relationship(back_populates="enrollments")
    placement_outcome: Mapped[PlacementOutcome | None] = relationship(
        back_populates="enrollment", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("candidate_id", "course_offering_id"),
        check_in("status", "status", EnrollmentStatus),
        CheckConstraint("completed_on >= enrolled_on", name="completed_after_enrolled"),
        CheckConstraint(
            "status <> 'COMPLETED' OR completed_on IS NOT NULL", name="completed_needs_date"
        ),
    )


class PlacementOutcome(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """What happened after training: placed or not, where, salary, still employed after 6 months."""

    __tablename__ = "placement_outcome"

    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enrollment.id", ondelete="CASCADE"), unique=True
    )
    placed: Mapped[bool]
    placement_type: Mapped[str | None] = mapped_column(String(16))
    employer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employer.id", ondelete="SET NULL"), index=True
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_role.id", ondelete="SET NULL"), index=True
    )
    salary_monthly_inr: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    placed_on: Mapped[date | None]
    retained_6m: Mapped[bool | None]
    related_to_training: Mapped[bool | None]
    verified: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    enrollment: Mapped[Enrollment] = relationship(back_populates="placement_outcome")
    employer: Mapped[Employer | None] = relationship()
    role: Mapped[JobRole | None] = relationship()
    rating: Mapped[EmployerRating | None] = relationship(
        back_populates="placement_outcome", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        check_in("placement_type", "placement_type", PlacementType),
        CheckConstraint("salary_monthly_inr >= 0", name="salary_not_negative"),
        # If not placed, there can be no employer, salary, type or placement date.
        CheckConstraint(
            "placed OR (placement_type IS NULL AND employer_id IS NULL "
            "AND salary_monthly_inr IS NULL AND placed_on IS NULL)",
            name="not_placed_has_no_details",
        ),
    )


class EmployerRating(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """An employer's 1-5 rating of a trainee they hired."""

    __tablename__ = "employer_rating"

    placement_outcome_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("placement_outcome.id", ondelete="CASCADE"), unique=True
    )
    employer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employer.id", ondelete="SET NULL"), index=True
    )
    rating: Mapped[int] = mapped_column(SmallInteger)
    skill_feedback: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    rated_on: Mapped[date | None]

    placement_outcome: Mapped[PlacementOutcome] = relationship(back_populates="rating")
    employer: Mapped[Employer | None] = relationship()

    __table_args__ = (
        between("rating_range", "rating", 1, 5),
        json_object("skill_feedback_is_object", "skill_feedback"),
    )
