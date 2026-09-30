"""Geography: districts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY
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
    from app.models.employers import Employer
    from app.models.training import Institute


class District(UUIDPrimaryKey, Timestamps, OfficialCode, Provenance, Base):
    """A district. `code` is OUR stable key (e.g. "MH-NASHIK"); the official LGD code goes in
    `official_code` (scheme "LGD") only after it has been verified."""

    __tablename__ = "district"

    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    state_name: Mapped[str] = mapped_column(String(100))
    # Other spellings / places that mean this district (e.g. "Nasik", "Ambad MIDC").
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'")
    )

    institutes: Mapped[list[Institute]] = relationship(back_populates="district")
    employers: Mapped[list[Employer]] = relationship(back_populates="district")

    __table_args__ = (
        UniqueConstraint("state_name", "name"),
        *official_code_rules("district"),
    )
