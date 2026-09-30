"""Models for config/synthetic.yaml (demo data generator settings)."""

from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from app.config.base import (
    ConfigModel,
    DistrictCode,
    Quarter,
    SectorCode,
    Text,
    duplicates,
    quarter_index,
    quarters_inclusive,
)
from app.models.enums import SectorEventType

SyntheticSourceId = Annotated[str, StringConstraints(pattern=r"^Y[0-9]{2}$")]
PatternId = Annotated[str, StringConstraints(pattern=r"^PP[0-9]+$")]
Count = Annotated[int, Field(ge=0)]


class History(ConfigModel):
    start_quarter: Quarter
    end_quarter: Quarter

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if quarter_index(self.start_quarter) > quarter_index(self.end_quarter):
            raise ValueError("history.start_quarter must not be after end_quarter")
        return self

    @property
    def quarter_count(self) -> int:
        return quarters_inclusive(self.start_quarter, self.end_quarter)


class CountRange(ConfigModel):
    min: Count
    max: Count

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) must not be greater than max ({self.max})")
        return self


class EmployersPerDistrict(ConfigModel):
    golden_path_district: Annotated[int, Field(ge=1)]
    other_districts: Count


class Volumes(ConfigModel):
    job_postings: Annotated[int, Field(ge=1)]
    employer_survey_responses: Count
    candidates: Annotated[int, Field(ge=1)]
    institutes: Annotated[int, Field(ge=1)]
    trainers_per_institute: CountRange
    employers_per_district: EmployersPerDistrict


class SourceIds(ConfigModel):
    job_postings: SyntheticSourceId
    employer_survey_responses: SyntheticSourceId
    consultations: SyntheticSourceId
    sector_events: SyntheticSourceId
    course_offerings: SyntheticSourceId
    trainers: SyntheticSourceId
    institute_equipment: SyntheticSourceId
    candidates: SyntheticSourceId
    enrollments: SyntheticSourceId
    placement_outcomes: SyntheticSourceId
    employer_ratings: SyntheticSourceId
    equipment_costs: SyntheticSourceId
    demo_vocabulary: SyntheticSourceId
    institutes: SyntheticSourceId
    employers: SyntheticSourceId

    @model_validator(mode="after")
    def _unique(self) -> Self:
        if repeated := duplicates(self.model_dump().values()):
            raise ValueError(f"each dataset needs its own source ID; repeated: {repeated}")
        return self


class PlantedPattern(ConfigModel):
    enabled: bool
    description: Text
    districts: Annotated[list[DistrictCode], Field(min_length=1)]
    sectors: Annotated[list[SectorCode], Field(min_length=1)]


class DemoEvent(ConfigModel):
    district: DistrictCode
    sector: SectorCode
    event_type: SectorEventType  # same values the database accepts
    title: Text
    expected_jobs: Annotated[int, Field(ge=0)]
    announced_quarter: Quarter


class SyntheticConfig(ConfigModel):
    seed: Annotated[int, Field(ge=0)]
    # Hand-written description of the demo world, and where exports are written
    # (both relative to the repository root).
    spec_file: Text
    export_dir: Text
    history: History
    volumes: Volumes
    source_ids: SourceIds
    planted_patterns: dict[PatternId, PlantedPattern]
    demo_event: DemoEvent
