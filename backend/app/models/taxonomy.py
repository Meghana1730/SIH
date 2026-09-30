"""The Skill Graph core: sectors, job roles, skills, aliases and the links between them."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
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
    EMBEDDING_DIM,
    Base,
    OfficialCode,
    Provenance,
    Timestamps,
    UUIDPrimaryKey,
    between,
    check_in,
    official_code_rules,
)
from app.models.enums import EdgeType, Language, SkillType

if TYPE_CHECKING:
    from app.models.qualifications import NosSkill


class Sector(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """An industry sector, e.g. Electrical, EV, Solar PV."""

    __tablename__ = "sector"

    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    # Name of the Sector Skill Council as free text (not an official identifier).
    ssc_name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)

    job_roles: Mapped[list[JobRole]] = relationship(back_populates="sector")


class JobRole(UUIDPrimaryKey, Timestamps, OfficialCode, Provenance, Base):
    """A job, e.g. "EV Charging Technician". The occupation code (e.g. NCO) goes in
    `official_code` once verified."""

    __tablename__ = "job_role"

    code: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    sector_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sector.id"), index=True)
    # NSQF-style level, e.g. 4 or 4.5. Official scale: TODO-VERIFY (docs/01-domain.md §3.4).
    nsqf_level: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'")
    )
    description: Mapped[str | None] = mapped_column(Text)

    sector: Mapped[Sector] = relationship(back_populates="job_roles")
    skill_links: Mapped[list[RoleSkill]] = relationship(
        back_populates="role", cascade="all, delete-orphan", passive_deletes=True
    )
    outgoing_edges: Mapped[list[RoleEdge]] = relationship(
        foreign_keys="RoleEdge.from_role_id",
        back_populates="from_role",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    incoming_edges: Mapped[list[RoleEdge]] = relationship(
        foreign_keys="RoleEdge.to_role_id",
        back_populates="to_role",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("nsqf_level > 0 AND nsqf_level <= 10", name="nsqf_level_range"),
        *official_code_rules("job_role"),
    )


class Skill(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """One teachable, checkable ability (docs/01-domain.md §4).
    Skills are the common language between jobs and courses."""

    __tablename__ = "skill"

    code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    skill_type: Mapped[str] = mapped_column(String(16))
    description: Mapped[str | None] = mapped_column(Text)
    # pgvector column. Reading it back gives a list-like vector of 384 numbers.
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    # Which model produced the embedding (vectors from different models must not be mixed).
    embedding_model: Mapped[str | None] = mapped_column(String(120))

    aliases: Mapped[list[SkillAlias]] = relationship(
        back_populates="skill", cascade="all, delete-orphan", passive_deletes=True
    )
    role_links: Mapped[list[RoleSkill]] = relationship(
        back_populates="skill", cascade="all, delete-orphan", passive_deletes=True
    )
    nos_links: Mapped[list[NosSkill]] = relationship(
        back_populates="skill", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        check_in("skill_type", "skill_type", SkillType),
        CheckConstraint(
            "(embedding IS NULL) = (embedding_model IS NULL)", name="embedding_model_recorded"
        ),
        # Fast "most similar skill" search by cosine distance (docs/04-architecture.md §3.6).
        Index(
            "ix_skill_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class SkillAlias(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """Another name for a skill, in English, Hindi or Marathi
    (e.g. "PV fitting", "सोलर पैनल लगाना")."""

    __tablename__ = "skill_alias"

    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(Text)
    # Cleaned form used for matching (lower-case, Unicode-normalised); computed by the app.
    alias_normalized: Mapped[str] = mapped_column(Text, index=True)
    language: Mapped[str] = mapped_column(String(8), default=Language.EN.value, server_default="en")
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120))

    skill: Mapped[Skill] = relationship(back_populates="aliases")

    __table_args__ = (
        # One alias text (per language) must point to exactly one skill, or matching is ambiguous.
        UniqueConstraint("language", "alias_normalized"),
        check_in("language", "language", Language),
        CheckConstraint("alias_normalized <> ''", name="alias_not_empty"),
        CheckConstraint(
            "(embedding IS NULL) = (embedding_model IS NULL)", name="embedding_model_recorded"
        ),
    )


class RoleSkill(Timestamps, Provenance, Base):
    """Which skills a job role needs, how important each one is, and at what level."""

    __tablename__ = "role_skill"

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_role.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    importance: Mapped[float]  # 0 (nice to have) .. 1 (essential)
    required_band: Mapped[int] = mapped_column(SmallInteger)  # 1 assist .. 4 lead

    role: Mapped[JobRole] = relationship(back_populates="skill_links")
    skill: Mapped[Skill] = relationship(back_populates="role_links")

    __table_args__ = (
        between("importance_range", "importance", 0, 1),
        between("required_band_range", "required_band", 1, 4),
    )


class RoleEdge(UUIDPrimaryKey, Timestamps, Provenance, Base):
    """A career step from one role to another (the career-path ladder).
    The skills to learn are the target role's skills that the source role lacks."""

    __tablename__ = "role_edge"

    from_role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_role.id", ondelete="CASCADE"), index=True
    )
    to_role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_role.id", ondelete="CASCADE"), index=True
    )
    edge_type: Mapped[str] = mapped_column(
        String(16), default=EdgeType.PROMOTION.value, server_default=EdgeType.PROMOTION.value
    )
    typical_training_hours: Mapped[int | None]
    note: Mapped[str | None] = mapped_column(Text)

    from_role: Mapped[JobRole] = relationship(
        foreign_keys=[from_role_id], back_populates="outgoing_edges"
    )
    to_role: Mapped[JobRole] = relationship(
        foreign_keys=[to_role_id], back_populates="incoming_edges"
    )

    __table_args__ = (
        UniqueConstraint("from_role_id", "to_role_id"),
        CheckConstraint("from_role_id <> to_role_id", name="no_self_loop"),
        check_in("edge_type", "edge_type", EdgeType),
        CheckConstraint("typical_training_hours > 0", name="training_hours_positive"),
    )
