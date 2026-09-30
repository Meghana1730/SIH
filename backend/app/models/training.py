"""Training supply: institutes, courses, modules, offerings (seats), trainers and equipment."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

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
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    OfficialCode,
    Provenance,
    Timestamps,
    UUIDPrimaryKey,
    academic_year_format,
    between,
    check_in,
    official_code_rules,
)
from app.models.enums import (
    CourseType,
    EquipmentCondition,
    InstituteType,
    MappingReviewStatus,
    Ownership,
)

if TYPE_CHECKING:
    from app.models.candidates import Enrollment
    from app.models.geography import District
    from app.models.qualifications import QualificationPack
    from app.models.taxonomy import JobRole, Sector, Skill


class Institute(UUIDPrimaryKey, Timestamps, OfficialCode, Provenance, Base):
    """An ITI, PMKVY training centre or polytechnic. Demo institutes are fictional
    ("Example ITI A") and marked is_synthetic."""

    __tablename__ = "institute"

    code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(250))
    institute_type: Mapped[str] = mapped_column(String(16))
    ownership: Mapped[str | None] = mapped_column(String(16))
    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("district.id"), index=True)

    district: Mapped[District] = relationship(back_populates="institutes")
    offerings: Mapped[list[CourseOffering]] = relationship(
        back_populates="institute", cascade="all, delete-orphan", passive_deletes=True
    )
    trainers: Mapped[list[Trainer]] = relationship(
        back_populates="institute", cascade="all, delete-orphan", passive_deletes=True
    )
    equipment_items: Mapped[list[InstituteEquipment]] = relationship(
        back_populates="institute", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        check_in("institute_type", "institute_type", InstituteType),
        check_in("ownership", "ownership", Ownership),
        *official_code_rules("institute"),
    )


class Course(UUIDPrimaryKey, Timestamps, OfficialCode, Provenance, Base):
    """A course definition (e.g. the DGT Electrician trade), independent of any institute."""

    __tablename__ = "course"

    code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(250))
    course_type: Mapped[str] = mapped_column(String(16))
    sector_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sector.id", ondelete="SET NULL"), index=True
    )
    qualification_pack_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("qualification_pack.id", ondelete="SET NULL"), index=True
    )
    duration_hours: Mapped[int | None]
    nsqf_level: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    syllabus_version: Mapped[str | None] = mapped_column(String(40))

    sector: Mapped[Sector | None] = relationship()
    qualification_pack: Mapped[QualificationPack | None] = relationship(back_populates="courses")
    modules: Mapped[list[CourseModule]] = relationship(
        back_populates="course",
        order_by="CourseModule.sequence",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    offerings: Mapped[list[CourseOffering]] = relationship(back_populates="course")
    role_links: Mapped[list[CourseRole]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        check_in("course_type", "course_type", CourseType),
        CheckConstraint("duration_hours > 0", name="duration_positive"),
        CheckConstraint("nsqf_level > 0 AND nsqf_level <= 10", name="nsqf_level_range"),
        *official_code_rules("course"),
    )


class CourseRole(Timestamps, Provenance, Base):
    """Which job roles a course prepares people for. Used to count training supply per role
    (docs/03-prd.md §7.3). Exactly one role per course can be the primary one."""

    __tablename__ = "course_role"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_role.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    is_primary: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    course: Mapped[Course] = relationship(back_populates="role_links")
    role: Mapped[JobRole] = relationship()

    __table_args__ = (
        Index(
            "uq_course_role_one_primary",
            "course_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )


class CourseModule(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """One module (chapter) of a course syllabus."""

    __tablename__ = "course_module"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(SmallInteger)  # 1, 2, 3 ... order in the syllabus
    title: Mapped[str] = mapped_column(String(300))
    hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    is_elective: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    description: Mapped[str | None] = mapped_column(Text)

    course: Mapped[Course] = relationship(back_populates="modules")
    skill_links: Mapped[list[ModuleSkill]] = relationship(
        back_populates="module", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("course_id", "sequence"),
        CheckConstraint("sequence >= 1", name="sequence_positive"),
        CheckConstraint("hours > 0", name="hours_positive"),
    )


class ModuleSkill(Timestamps, Provenance, Base):
    """Which skills a module teaches, and at what band (1 assist .. 4 lead)."""

    __tablename__ = "module_skill"

    module_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_module.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    band_taught: Mapped[int] = mapped_column(SmallInteger)
    review_status: Mapped[str] = mapped_column(
        String(16),
        default=MappingReviewStatus.APPROVED.value,
        server_default=MappingReviewStatus.APPROVED.value,
    )

    module: Mapped[CourseModule] = relationship(back_populates="skill_links")
    skill: Mapped[Skill] = relationship()

    __table_args__ = (
        between("band_taught_range", "band_taught", 1, 4),
        check_in("review_status", "review_status", MappingReviewStatus),
    )


class CourseOffering(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """A course run by an institute in one academic year, with its seats (training supply)."""

    __tablename__ = "course_offering"

    institute_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institute.id", ondelete="CASCADE"), index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course.id"), index=True)
    academic_year: Mapped[str] = mapped_column(String(7))  # e.g. "2025-26"
    seats: Mapped[int]
    seats_filled: Mapped[int | None]
    completion_rate: Mapped[float | None]  # 0..1

    institute: Mapped[Institute] = relationship(back_populates="offerings")
    course: Mapped[Course] = relationship(back_populates="offerings")
    enrollments: Mapped[list[Enrollment]] = relationship(
        back_populates="course_offering", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("institute_id", "course_id", "academic_year"),
        academic_year_format("academic_year_format", "academic_year"),
        CheckConstraint("seats >= 0", name="seats_not_negative"),
        CheckConstraint(
            "seats_filled >= 0 AND seats_filled <= seats", name="seats_filled_within_seats"
        ),
        between("completion_rate_range", "completion_rate", 0, 1),
    )


class Trainer(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """A trainer, identified only by a pseudonym such as "T-01" (no personal data)."""

    __tablename__ = "trainer"

    institute_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institute.id", ondelete="CASCADE"), index=True
    )
    pseudonym: Mapped[str] = mapped_column(String(40))
    certifications: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'")
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    institute: Mapped[Institute] = relationship(back_populates="trainers")
    skill_links: Mapped[list[TrainerSkill]] = relationship(
        back_populates="trainer", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("institute_id", "pseudonym"),
        CheckConstraint("pseudonym <> ''", name="pseudonym_not_empty"),
    )


class TrainerSkill(Timestamps, Provenance, Base):
    """Which skills a trainer can teach, and up to which band."""

    __tablename__ = "trainer_skill"

    trainer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trainer.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    band: Mapped[int] = mapped_column(SmallInteger)

    trainer: Mapped[Trainer] = relationship(back_populates="skill_links")
    skill: Mapped[Skill] = relationship()

    __table_args__ = (between("band_range", "band", 1, 4),)


class Equipment(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """A tool or training kit (e.g. from a DGT syllabus equipment list)."""

    __tablename__ = "equipment"

    code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(80))
    indicative_cost_inr: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    # Costs are team estimates unless stated otherwise (docs/03-prd.md FR-10.3).
    cost_is_estimate: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    skill_links: Mapped[list[SkillEquipment]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (CheckConstraint("indicative_cost_inr >= 0", name="cost_not_negative"),)


class SkillEquipment(Timestamps, Provenance, Base):
    """Equipment needed to teach a skill, per training batch."""

    __tablename__ = "skill_equipment"

    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill.id", ondelete="CASCADE"), primary_key=True
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    qty_per_batch: Mapped[int] = mapped_column(default=1, server_default=text("1"))

    skill: Mapped[Skill] = relationship()
    equipment: Mapped[Equipment] = relationship(back_populates="skill_links")

    __table_args__ = (CheckConstraint("qty_per_batch > 0", name="qty_positive"),)


class InstituteEquipment(Timestamps, Provenance, Base):
    """Equipment an institute already has."""

    __tablename__ = "institute_equipment"

    institute_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institute.id", ondelete="CASCADE"), primary_key=True
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    quantity: Mapped[int]
    condition: Mapped[str] = mapped_column(
        String(16),
        default=EquipmentCondition.WORKING.value,
        server_default=EquipmentCondition.WORKING.value,
    )

    institute: Mapped[Institute] = relationship(back_populates="equipment_items")
    equipment: Mapped[Equipment] = relationship()

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity_not_negative"),
        check_in("condition", "condition", EquipmentCondition),
    )
