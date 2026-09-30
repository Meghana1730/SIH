"""Official qualification standards: Qualification Packs (QP) and National Occupational
Standards (NOS). Official codes are stored only after verification on the NQR."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    OfficialCode,
    Provenance,
    Timestamps,
    UUIDPrimaryKey,
    official_code_rules,
)

if TYPE_CHECKING:
    from app.models.taxonomy import JobRole, Sector, Skill
    from app.models.training import Course


class QualificationPack(UUIDPrimaryKey, Timestamps, OfficialCode, Provenance, Base):
    """The official standard for one job role (a "recipe card" made of NOS units)."""

    __tablename__ = "qualification_pack"

    code: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    sector_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sector.id", ondelete="SET NULL"), index=True
    )
    job_role_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_role.id", ondelete="SET NULL"), index=True
    )
    # Awarding body / SSC name as free text.
    awarding_body: Mapped[str | None] = mapped_column(String(200))
    nsqf_level: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    version: Mapped[str | None] = mapped_column(String(20))
    valid_until: Mapped[date | None]
    document_url: Mapped[str | None] = mapped_column(Text)

    sector: Mapped[Sector | None] = relationship()
    job_role: Mapped[JobRole | None] = relationship()
    nos_units: Mapped[list[Nos]] = relationship(
        back_populates="qualification_pack", cascade="all, delete-orphan", passive_deletes=True
    )
    courses: Mapped[list[Course]] = relationship(back_populates="qualification_pack")

    __table_args__ = (
        CheckConstraint("nsqf_level > 0 AND nsqf_level <= 10", name="nsqf_level_range"),
        # A verified QP code is unique per version.
        *official_code_rules("qualification_pack", "version"),
    )


class Nos(UUIDPrimaryKey, Timestamps, OfficialCode, Provenance, Base):
    """One unit of competence inside a Qualification Pack."""

    __tablename__ = "nos"

    code: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    qualification_pack_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("qualification_pack.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str | None] = mapped_column(Text)

    qualification_pack: Mapped[QualificationPack] = relationship(back_populates="nos_units")
    skill_links: Mapped[list[NosSkill]] = relationship(
        back_populates="nos", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = official_code_rules("nos")


class NosSkill(Timestamps, Provenance, Base):
    """Which skills of our Skill Graph a NOS unit covers."""

    __tablename__ = "nos_skill"

    nos_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nos.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill.id", ondelete="CASCADE"), primary_key=True, index=True
    )

    nos: Mapped[Nos] = relationship(back_populates="skill_links")
    skill: Mapped[Skill] = relationship(back_populates="nos_links")
