"""Models for config/scope.yaml (districts and languages)."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from app.config.base import ConfigModel, DistrictCode, Text, duplicates
from app.models.enums import Language  # the languages the database accepts


class DistrictEntry(ConfigModel):
    code: DistrictCode
    name: Text
    aliases: list[Text]


class LanguageSettings(ConfigModel):
    supported: Annotated[list[Language], Field(min_length=1)]
    default: Language
    candidate_ui: Annotated[list[Language], Field(min_length=1)]
    employer_ui: Annotated[list[Language], Field(min_length=1)]
    staff_ui: Annotated[list[Language], Field(min_length=1)]
    district_plan_pdf: Annotated[list[Language], Field(min_length=1)]

    @model_validator(mode="after")
    def _within_supported(self) -> Self:
        supported = set(self.supported)
        if self.default not in supported:
            raise ValueError(f"default language '{self.default}' is not in supported")
        for field in ("candidate_ui", "employer_ui", "staff_ui", "district_plan_pdf"):
            extra = set(getattr(self, field)) - supported
            if extra:
                raise ValueError(f"{field} uses languages not in supported: {sorted(extra)}")
            if duplicates(getattr(self, field)):
                raise ValueError(f"{field} lists a language twice")
        return self


class ScopeConfig(ConfigModel):
    state: Text
    districts: Annotated[list[DistrictEntry], Field(min_length=1)]
    golden_path_district: DistrictCode
    languages: LanguageSettings

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if repeated := duplicates(d.code for d in self.districts):
            raise ValueError(f"district codes must be unique; repeated: {repeated}")
        # A name or alias must point to exactly one district, or location matching is ambiguous.
        names = [n.casefold() for d in self.districts for n in [d.name, *d.aliases]]
        if repeated := duplicates(names):
            raise ValueError(f"district names/aliases must be unique; repeated: {repeated}")
        if self.golden_path_district not in self.district_codes:
            raise ValueError(
                f"golden_path_district '{self.golden_path_district}' is not one of the "
                f"districts {self.district_codes}"
            )
        return self

    @property
    def district_codes(self) -> list[str]:
        return [district.code for district in self.districts]
