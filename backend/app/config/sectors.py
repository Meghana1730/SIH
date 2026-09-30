"""Models for config/sectors.yaml."""

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from app.config.base import ConfigModel, Fraction, SectorCode, Text, duplicates, require_sum_to_one

RoleCode = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")]


class SectorEntry(ConfigModel):
    code: SectorCode
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    description: Text


class EventStaffing(ConfigModel):
    fallback: Literal["even_split_across_sector_roles"]
    # {SECTOR_CODE: {role_code: share}}; each sector's shares must add up to 1.0.
    patterns: dict[SectorCode, dict[RoleCode, Fraction]]

    @model_validator(mode="after")
    def _shares_sum_to_one(self) -> Self:
        for sector, shares in self.patterns.items():
            if not shares:
                raise ValueError(f"event_staffing.patterns.{sector} is empty")
            require_sum_to_one(shares, f"event_staffing.patterns.{sector} role shares")
        return self


class SectorsConfig(ConfigModel):
    sectors: Annotated[list[SectorEntry], Field(min_length=1)]
    event_staffing: EventStaffing

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if repeated := duplicates(s.code for s in self.sectors):
            raise ValueError(f"sector codes must be unique; repeated: {repeated}")
        if repeated := duplicates(s.name for s in self.sectors):
            raise ValueError(f"sector names must be unique; repeated: {repeated}")
        unknown = set(self.event_staffing.patterns) - set(self.codes)
        if unknown:
            raise ValueError(
                f"event_staffing.patterns uses unknown sector codes {sorted(unknown)}; "
                f"known: {self.codes}"
            )
        return self

    @property
    def codes(self) -> list[str]:
        return [sector.code for sector in self.sectors]
