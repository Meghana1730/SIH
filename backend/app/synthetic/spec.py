"""The demo-world spec (data/synthetic/spec/demo_world.yaml), validated with Pydantic.

The spec is hand-written: it fixes every COUNT that makes a planted pattern (postings per
quarter, seats, completion and placement rates, survey headcounts). The generator only adds
seeded details on top, so the patterns hold for any seed.

    spec = load_spec(path)                       # SpecError if the file is invalid
    problems = check_spec_against_config(spec, config)
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, StringConstraints, ValidationError, model_validator

from app.config import ProductConfig
from app.config.base import (
    ConfigModel,
    DistrictCode,
    Fraction,
    Quarter,
    SectorCode,
    Text,
    duplicates,
    quarter_index,
)
from app.config.sectors import RoleCode
from app.config.yaml_loader import DuplicateKeyError, load_yaml_text
from app.models.enums import (
    CourseType,
    EdgeType,
    EducationLevel,
    EmployerSize,
    EquipmentCondition,
    InsightType,
    InstituteType,
    Language,
    Ownership,
    ParticipantType,
    PlacementType,
    SectorEventType,
    SkillType,
    SurveyChannel,
    Willingness,
)
from app.nlp.text import normalize_text

Code = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")]
EntityCode = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9][A-Z0-9-]{1,79}$")]
Key = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")]
AcademicYear = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-[0-9]{2}$")]
Band = Annotated[int, Field(ge=1, le=4)]
Count = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class SpecError(Exception):
    """The spec file is missing, not valid YAML, or breaks a rule."""


def _shares_sum_to_one(shares: dict, label: str) -> None:
    total = sum(shares.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"{label} must add up to 1.0 but add up to {total:g}")


class IntRange(ConfigModel):
    min: Count
    max: Count

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) must not be greater than max ({self.max})")
        return self


# --------------------------------------------------------------------------- geography
class DistrictSpec(ConfigModel):
    spellings: Annotated[list[Text], Field(min_length=1)]
    areas: Annotated[list[Text], Field(min_length=1)]
    salary_factor: Annotated[float, Field(gt=0.5, lt=2)]
    posting_languages: dict[Language, Fraction]

    @model_validator(mode="after")
    def _languages(self) -> Self:
        _shares_sum_to_one(self.posting_languages, "posting_languages")
        if Language.EN not in self.posting_languages:
            raise ValueError("posting_languages must include en")
        return self


# --------------------------------------------------------------------------- vocabulary
class SkillSpec(ConfigModel):
    code: Code
    name: Title
    type: SkillType
    description: Text
    aliases: dict[Language, list[Text]] = {}


class RoleSkillSpec(ConfigModel):
    skill: Code
    importance: Fraction
    band: Band
    posting_share: Fraction  # share of the role's job ads that name this skill


class RoleSpec(ConfigModel):
    code: RoleCode
    title: Title
    sector: SectorCode
    description: Text
    aliases: list[Text]
    titles: dict[Language, Annotated[list[Title], Field(min_length=1)]]
    salary_monthly_inr: IntRange
    experience_years: Annotated[list[tuple[Count, Count]], Field(min_length=1)]
    skills: Annotated[list[RoleSkillSpec], Field(min_length=1)]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if Language.EN not in self.titles:
            raise ValueError(f"role {self.code}: titles must include en")
        if repeated := duplicates(s.skill for s in self.skills):
            raise ValueError(f"role {self.code} lists a skill twice: {repeated}")
        if not any(s.posting_share == 1.0 for s in self.skills):
            raise ValueError(f"role {self.code} needs at least one skill with posting_share 1.0")
        for low, high in self.experience_years:
            if low > high:
                raise ValueError(f"role {self.code}: experience range {low}-{high} is reversed")
        return self

    def skill(self, code: str) -> RoleSkillSpec | None:
        return next((s for s in self.skills if s.skill == code), None)


class CareerStepSpec(ConfigModel):
    from_role: Annotated[RoleCode, Field(alias="from")]
    to_role: Annotated[RoleCode, Field(alias="to")]
    type: EdgeType
    training_hours: PositiveInt | None  # None = a full programme (not modelled in hours)
    note: Text


class EquipmentSpec(ConfigModel):
    code: EntityCode
    name: Title
    category: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    cost_inr: PositiveInt  # a rough team estimate, never an official price
    skills: Annotated[dict[Code, PositiveInt], Field(min_length=1)]


# --------------------------------------------------------------------------- training
class ModuleSpec(ConfigModel):
    title: Title
    hours: PositiveInt
    skills: Annotated[dict[Code, Band], Field(min_length=1)]


class CourseSpec(ConfigModel):
    code: Code
    name: Title
    type: CourseType
    sector: SectorCode
    primary_role: RoleCode
    secondary_roles: list[RoleCode]
    syllabus_version: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    delivery: Literal["annual", "short"]
    duration_days: PositiveInt | None = None  # short courses only
    programme_years: PositiveInt | None = None  # annual (ITI) programmes only
    # Total course hours (an assumption), or None when not modelled; NOT the sum of the
    # few demo modules for a multi-year trade.
    duration_hours: PositiveInt | None
    trainers_per_offering: PositiveInt
    trainer_certifications: list[Text]
    placement_types: dict[PlacementType, Fraction]
    modules: Annotated[list[ModuleSpec], Field(min_length=1)]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if (self.delivery == "short") != (self.duration_days is not None):
            raise ValueError(f"course {self.code}: duration_days is needed only for short courses")
        if (self.delivery == "annual") != (self.programme_years is not None):
            raise ValueError(
                f"course {self.code}: programme_years is needed only for annual programmes"
            )
        if self.primary_role in self.secondary_roles:
            raise ValueError(f"course {self.code}: the primary role is also a secondary role")
        if repeated := duplicates(m.title for m in self.modules):
            raise ValueError(f"course {self.code} repeats module titles: {repeated}")
        _shares_sum_to_one(self.placement_types, f"course {self.code} placement_types")
        return self

    @property
    def taught_bands(self) -> dict[str, int]:
        """Skill -> highest band taught in any module."""
        bands: dict[str, int] = {}
        for module in self.modules:
            for skill, band in module.skills.items():
                bands[skill] = max(band, bands.get(skill, 0))
        return bands


class CohortSpec(ConfigModel):
    filled: Count
    completion: Fraction
    placement: Fraction  # placed / completed
    retention_6m: Fraction | None = None  # default: outcomes.retention_6m


class OfferingSpec(ConfigModel):
    course: Code
    seats: Count
    cohorts: Annotated[dict[AcademicYear, CohortSpec], Field(min_length=1)]

    @model_validator(mode="after")
    def _filled_within_seats(self) -> Self:
        for year, cohort in self.cohorts.items():
            if cohort.filled > self.seats:
                raise ValueError(
                    f"offering {self.course} {year}: filled ({cohort.filled}) > seats "
                    f"({self.seats})"
                )
            start, end = int(year[:4]), int(year[5:])
            if (start + 1) % 100 != end:
                raise ValueError(f"academic year {year} must span two consecutive years")
        return self


class InstituteSpec(ConfigModel):
    code: EntityCode
    name: Title
    type: InstituteType
    ownership: Ownership
    district: DistrictCode
    offerings: Annotated[list[OfferingSpec], Field(min_length=1)]


# --------------------------------------------------------------------------- employers
class EmployerSpec(ConfigModel):
    code: EntityCode
    name: Title
    district: DistrictCode
    sector: SectorCode
    size: EmployerSize
    msme: bool
    business_type: Annotated[str, StringConstraints(min_length=1, max_length=60)]
    language: Language
    apprenticeship: Willingness
    apprentices_possible: Count
    # role -> (headcount in the first survey quarter, headcount in the last one)
    survey_roles: Annotated[dict[RoleCode, tuple[Count, Count]], Field(min_length=1)]
    # skill -> first quarter the employer names it (None = from the start)
    survey_skills: dict[Code, Quarter | None]


# --------------------------------------------------------------------------- postings
class PostingSettings(ConfigModel):
    directory_employer_share: Fraction
    # A demo employer posts at most ceil(its survey headcount / 4) + this many ads a quarter.
    directory_ads_slack: Count
    employer_pool_size: PositiveInt
    employer_pool_names: dict[SectorCode, Title]
    salary_stated_share: Fraction
    text: dict[Language, Text]
    experience_text: dict[Language, Text]
    salary_text: dict[Language, Text]
    hardest_skills_text: dict[Language, Text]

    @model_validator(mode="after")
    def _all_languages(self) -> Self:
        for field in ("text", "experience_text", "salary_text", "hardest_skills_text"):
            missing = set(Language) - set(getattr(self, field))
            if missing:
                raise ValueError(f"postings.{field} misses languages {sorted(missing)}")
        return self


class OutcomeSettings(ConfigModel):
    related_to_training_share: Fraction
    retention_6m: Fraction
    employer_link_share: Fraction
    # course code (or "default") -> mean employer rating, 1..5
    rating_mean: dict[str, Annotated[float, Field(ge=1, le=5)]]

    @model_validator(mode="after")
    def _has_default(self) -> Self:
        if "default" not in self.rating_mean:
            raise ValueError("outcomes.rating_mean needs a 'default' entry")
        return self


class DetailSettings(ConfigModel):
    survey_channels: dict[SurveyChannel, Fraction]
    equipment_condition: dict[EquipmentCondition, Fraction]
    candidate_education: dict[CourseType, dict[EducationLevel, Fraction]]
    candidate_languages: dict[Language, Fraction]
    contact_consent_share: Fraction
    placement_delay_days: IntRange

    @model_validator(mode="after")
    def _shares(self) -> Self:
        _shares_sum_to_one(self.survey_channels, "details.survey_channels")
        _shares_sum_to_one(self.equipment_condition, "details.equipment_condition")
        for course_type, shares in self.candidate_education.items():
            _shares_sum_to_one(shares, f"details.candidate_education.{course_type}")
        return self


# --------------------------------------------------------------------------- events etc.
class EventSpec(ConfigModel):
    key: Key
    district: DistrictCode
    sector: SectorCode
    type: SectorEventType
    title: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    description: Text
    expected_jobs: Count
    announced_on: date
    realization_factor: Fraction | None


class InsightSpec(ConfigModel):
    type: InsightType
    skill: Code | None
    summary: Text


class ConsultationSpec(ConfigModel):
    key: Key
    title: Annotated[str, StringConstraints(min_length=1, max_length=250)]
    held_on: date
    district: DistrictCode
    sector: SectorCode
    participant: ParticipantType
    notes: Text
    insights: list[InsightSpec]


class GoldenCourseTarget(ConfigModel):
    institute: EntityCode
    course: Code
    ev_role: RoleCode
    modules: Annotated[list[Title], Field(min_length=1)]


class DistrictRoleTarget(ConfigModel):
    district: DistrictCode
    role: RoleCode


class DecliningTarget(ConfigModel):
    skill: Code
    role: RoleCode


class PatternTargets(ConfigModel):
    ev_skills: Annotated[list[Code], Field(min_length=1)]
    solar_skills: list[Code]
    golden_course: GoldenCourseTarget
    oversupply: DistrictRoleTarget
    declining: DecliningTarget
    event: Key
    ev_training_institute: EntityCode


class SanityLimits(ConfigModel):
    monthly_salary_inr: IntRange
    seats_per_offering: IntRange


# --------------------------------------------------------------------------- the world
class WorldSpec(ConfigModel):
    as_of: date
    generated_at: AwareDatetime
    license_note: Text
    districts: dict[DistrictCode, DistrictSpec]
    skills: Annotated[list[SkillSpec], Field(min_length=1)]
    roles: Annotated[list[RoleSpec], Field(min_length=1)]
    career_steps: list[CareerStepSpec]
    equipment: list[EquipmentSpec]
    courses: Annotated[list[CourseSpec], Field(min_length=1)]
    institutes: Annotated[list[InstituteSpec], Field(min_length=1)]
    employers: Annotated[list[EmployerSpec], Field(min_length=1)]
    posting_schedule: dict[DistrictCode, dict[RoleCode, list[Count]]]
    postings: PostingSettings
    outcomes: OutcomeSettings
    details: DetailSettings
    sector_events: list[EventSpec]
    consultations: list[ConsultationSpec]
    pattern_targets: PatternTargets
    sanity: SanityLimits

    # -------- lookups
    def role(self, code: str) -> RoleSpec:
        return next(r for r in self.roles if r.code == code)

    def course(self, code: str) -> CourseSpec:
        return next(c for c in self.courses if c.code == code)

    def institute(self, code: str) -> InstituteSpec:
        return next(i for i in self.institutes if i.code == code)

    @model_validator(mode="after")
    def _references(self) -> Self:
        """Every code used anywhere must be defined exactly once."""
        problems: list[str] = []

        def unique(label: str, values: list[str]) -> None:
            if repeated := duplicates(values):
                problems.append(f"{label} must be unique; repeated: {repeated}")

        skills = {s.code for s in self.skills}
        roles = {r.code for r in self.roles}
        courses = {c.code for c in self.courses}
        unique("skill codes", [s.code for s in self.skills])
        unique("skill names", [s.name.casefold() for s in self.skills])
        unique("role codes", [r.code for r in self.roles])
        unique("course codes", [c.code for c in self.courses])
        unique("equipment codes", [e.code for e in self.equipment])
        unique("institute codes", [i.code for i in self.institutes])
        unique("institute names", [i.name for i in self.institutes])
        unique("employer codes", [e.code for e in self.employers])
        unique("employer names", [e.name for e in self.employers])
        unique("event keys", [e.key for e in self.sector_events])
        unique("consultation keys", [c.key for c in self.consultations])
        unique("career steps", [f"{s.from_role}->{s.to_role}" for s in self.career_steps])

        # An alias (per language) must point to exactly one skill, and must not repeat
        # another skill's name, or skill matching becomes ambiguous.
        per_language: Counter[tuple[str, str]] = Counter()
        names = {normalize_text(s.name): s.code for s in self.skills}
        for skill in self.skills:
            for language, aliases in skill.aliases.items():
                for alias in aliases:
                    normalized = normalize_text(alias)
                    if not normalized:
                        problems.append(f"skill {skill.code}: alias '{alias}' is empty")
                    per_language[(language.value, normalized)] += 1
                    owner = names.get(normalized)
                    if owner is not None:
                        problems.append(
                            f"skill {skill.code}: alias '{alias}' equals the name of {owner}"
                        )
        repeated_aliases = sorted(
            f"{lang}:{text}" for (lang, text), n in per_language.items() if n > 1
        )
        if repeated_aliases:
            problems.append(f"aliases must be unique per language; repeated: {repeated_aliases}")

        def need(kind: str, value: str, known: set[str], where: str) -> None:
            if value not in known:
                problems.append(f"{where}: unknown {kind} '{value}'")

        for role in self.roles:
            for link in role.skills:
                need("skill", link.skill, skills, f"role {role.code}")
        for step in self.career_steps:
            need("role", step.from_role, roles, "career_steps")
            need("role", step.to_role, roles, "career_steps")
            if step.from_role == step.to_role:
                problems.append(f"career step {step.from_role} points to itself")
        for item in self.equipment:
            for skill in item.skills:
                need("skill", skill, skills, f"equipment {item.code}")
        for course in self.courses:
            for role in [course.primary_role, *course.secondary_roles]:
                need("role", role, roles, f"course {course.code}")
            for module in course.modules:
                for skill in module.skills:
                    need("skill", skill, skills, f"course {course.code} module '{module.title}'")
        for institute in self.institutes:
            need("district", institute.district, set(self.districts), f"institute {institute.code}")
            unique(f"courses of {institute.code}", [o.course for o in institute.offerings])
            for offering in institute.offerings:
                need("course", offering.course, courses, f"institute {institute.code}")
        for employer in self.employers:
            need("district", employer.district, set(self.districts), f"employer {employer.code}")
            for role in employer.survey_roles:
                need("role", role, roles, f"employer {employer.code}")
            for skill in employer.survey_skills:
                need("skill", skill, skills, f"employer {employer.code}")
        for district, schedule in self.posting_schedule.items():
            need("district", district, set(self.districts), "posting_schedule")
            for role in schedule:
                need("role", role, roles, f"posting_schedule.{district}")
        for event in self.sector_events:
            need("district", event.district, set(self.districts), f"sector_event {event.key}")
        for consultation in self.consultations:
            for insight in consultation.insights:
                if insight.skill is not None:
                    need("skill", insight.skill, skills, f"consultation {consultation.key}")
        for rating_key in self.outcomes.rating_mean:
            if rating_key != "default":
                need("course", rating_key, courses, "outcomes.rating_mean")

        targets = self.pattern_targets
        for skill in [*targets.ev_skills, *targets.solar_skills, targets.declining.skill]:
            need("skill", skill, skills, "pattern_targets")
        for role in [
            targets.golden_course.ev_role,
            targets.oversupply.role,
            targets.declining.role,
        ]:
            need("role", role, roles, "pattern_targets")
        need("course", targets.golden_course.course, courses, "pattern_targets.golden_course")
        institute_codes = {i.code for i in self.institutes}
        need("institute", targets.golden_course.institute, institute_codes, "pattern_targets")
        need("institute", targets.ev_training_institute, institute_codes, "pattern_targets")
        need("event", targets.event, {e.key for e in self.sector_events}, "pattern_targets")

        if self.generated_at.date() < self.as_of:
            problems.append("generated_at must not be before as_of")
        if problems:
            raise ValueError("\n".join(problems))
        return self


# --------------------------------------------------------------------------- loading
def load_spec(path: Path) -> WorldSpec:
    try:
        raw = load_yaml_text(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SpecError(f"Spec file not found: {path}") from exc
    except DuplicateKeyError as exc:
        raise SpecError(f"{path}: {exc}") from exc
    except ValueError as exc:
        raise SpecError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise SpecError(f"{path} must contain a YAML mapping")
    try:
        return WorldSpec.model_validate(raw)
    except ValidationError as exc:
        lines = []
        for error in exc.errors():
            where = ".".join(str(part) for part in error["loc"]) or "(top level)"
            lines.append(f"  - {where}: {error['msg']}")
        raise SpecError(f"{path} is invalid:\n" + "\n".join(lines)) from exc


def check_spec_against_config(spec: WorldSpec, config: ProductConfig) -> list[str]:
    """Rules that involve config/*.yaml (districts, sectors, history, volume targets)."""
    problems: list[str] = []
    synthetic = config.synthetic
    districts = set(config.scope.district_codes)
    sectors = set(config.sectors.codes)
    quarters = synthetic.history.quarter_count
    volumes = synthetic.volumes

    def district_ok(code: str, where: str) -> None:
        if code not in districts:
            problems.append(f"{where}: district '{code}' is not in config/scope.yaml")

    def sector_ok(code: str, where: str) -> None:
        if code not in sectors:
            problems.append(f"{where}: sector '{code}' is not in config/sectors.yaml")

    for code in spec.districts:
        district_ok(code, "districts")
    missing = districts - set(spec.districts)
    if missing:
        problems.append(f"districts: no entry for {sorted(missing)}")
    for role in spec.roles:
        sector_ok(role.sector, f"role {role.code}")
    for course in spec.courses:
        sector_ok(course.sector, f"course {course.code}")
    for employer in spec.employers:
        sector_ok(employer.sector, f"employer {employer.code}")
    for event in spec.sector_events:
        sector_ok(event.sector, f"sector_event {event.key}")
        district_ok(event.district, f"sector_event {event.key}")
    for consultation in spec.consultations:
        sector_ok(consultation.sector, f"consultation {consultation.key}")
        district_ok(consultation.district, f"consultation {consultation.key}")
    for sector in spec.postings.employer_pool_names:
        sector_ok(sector, "postings.employer_pool_names")
    for sector in {r.sector for r in spec.roles} - set(spec.postings.employer_pool_names):
        problems.append(f"postings.employer_pool_names has no name for sector {sector}")

    # Time frame
    end = synthetic.history.end_quarter
    as_of_quarter = f"{spec.as_of.year}Q{(spec.as_of.month - 1) // 3 + 1}"
    if as_of_quarter != end:
        problems.append(f"as_of ({spec.as_of}) must fall in the last history quarter {end}")
    for district, schedule in spec.posting_schedule.items():
        for role, counts in schedule.items():
            if len(counts) != quarters:
                problems.append(
                    f"posting_schedule.{district}.{role} has {len(counts)} values; the "
                    f"history has {quarters} quarters"
                )
    start_index = quarter_index(synthetic.history.start_quarter)
    for employer in spec.employers:
        for skill, first in employer.survey_skills.items():
            if first is not None and not start_index <= quarter_index(first) <= quarter_index(end):
                problems.append(f"employer {employer.code}: {skill} starts outside the history")
    for event in spec.sector_events:
        if event.announced_on > spec.as_of:
            problems.append(f"sector_event {event.key} is announced after as_of")
    for consultation in spec.consultations:
        if consultation.held_on > spec.as_of:
            problems.append(f"consultation {consultation.key} is held after as_of")
    for institute in spec.institutes:
        for offering in institute.offerings:
            for year in offering.cohorts:
                # A cohort must have finished (July of its second year) by as_of.
                if date(int(year[:4]) + 1, 7, 31) > spec.as_of:
                    problems.append(
                        f"institute {institute.code} {offering.course} {year}: the cohort "
                        f"ends after as_of"
                    )

    # Volume targets (docs/03-prd.md §10.2)
    postings = sum(sum(c) for schedule in spec.posting_schedule.values() for c in schedule.values())
    if postings < volumes.job_postings:
        problems.append(
            f"posting_schedule adds up to {postings} postings; target {volumes.job_postings}"
        )
    responses = len(spec.employers) * quarters
    if responses < volumes.employer_survey_responses:
        problems.append(f"{responses} survey responses; target {volumes.employer_survey_responses}")
    candidates = sum(
        c.filled for i in spec.institutes for o in i.offerings for c in o.cohorts.values()
    )
    if candidates < volumes.candidates:
        problems.append(f"{candidates} candidates (seats filled); target {volumes.candidates}")
    if len(spec.institutes) < volumes.institutes:
        problems.append(f"{len(spec.institutes)} institutes; target {volumes.institutes}")
    per_district = Counter(e.district for e in spec.employers)
    golden = config.scope.golden_path_district
    for district in sorted(districts):
        target = (
            volumes.employers_per_district.golden_path_district
            if district == golden
            else volumes.employers_per_district.other_districts
        )
        if per_district[district] < target:
            problems.append(f"{per_district[district]} employers in {district}; target {target}")
    trainer_range = volumes.trainers_per_institute
    for institute in spec.institutes:
        trainers = sum(spec.course(o.course).trainers_per_offering for o in institute.offerings)
        if not trainer_range.min <= trainers <= trainer_range.max:
            problems.append(
                f"institute {institute.code} gets {trainers} trainers; config allows "
                f"{trainer_range.min}-{trainer_range.max}"
            )
    problems += _pattern_problems(spec, config)
    problems += _cross_reference_problems(spec)
    seat_limits = spec.sanity.seats_per_offering
    for institute in spec.institutes:
        for offering in institute.offerings:
            if not seat_limits.min <= offering.seats <= seat_limits.max:
                problems.append(f"institute {institute.code} {offering.course}: seats out of range")
    return problems


def _pattern_problems(spec: WorldSpec, config: ProductConfig) -> list[str]:
    """pattern_targets must agree with the enabled planted patterns in config/synthetic.yaml,
    or the validator would check a pattern in the wrong place."""
    problems: list[str] = []
    patterns = config.synthetic.planted_patterns
    targets = spec.pattern_targets
    roles = {r.code: r for r in spec.roles}
    institutes = {i.code: i for i in spec.institutes}
    courses = {c.code: c for c in spec.courses}
    events = {e.key: e for e in spec.sector_events}

    def expect(pattern_id: str, district: str | None, sector: str | None, what: str) -> None:
        pattern = patterns.get(pattern_id)
        if pattern is None or not pattern.enabled:
            return
        if district is not None and district not in pattern.districts:
            problems.append(
                f"pattern_targets ({what}): district {district} is not in {pattern_id} districts"
            )
        if sector is not None and sector not in pattern.sectors:
            problems.append(
                f"pattern_targets ({what}): sector {sector} is not in {pattern_id} sectors"
            )

    golden = institutes.get(targets.golden_course.institute)
    course = courses.get(targets.golden_course.course)
    expect(
        "PP2",
        golden.district if golden else None,
        course.sector if course else None,
        "golden_course",
    )
    oversupply_role = roles.get(targets.oversupply.role)
    expect(
        "PP3",
        targets.oversupply.district,
        oversupply_role.sector if oversupply_role else None,
        "oversupply",
    )
    declining_role = roles.get(targets.declining.role)
    expect("PP4", None, declining_role.sector if declining_role else None, "declining")
    event = events.get(targets.event)
    if event is not None:
        expect("PP5", event.district, event.sector, "event")
    ev_institute = institutes.get(targets.ev_training_institute)
    expect("PP6", ev_institute.district if ev_institute else None, None, "ev_training_institute")
    pp1 = patterns.get("PP1")
    if pp1 is not None and pp1.enabled and "SOLAR_PV" in pp1.sectors and not targets.solar_skills:
        problems.append("PP1 includes SOLAR_PV but pattern_targets.solar_skills is empty")
    pp7 = patterns.get("PP7")
    if pp7 is not None and pp7.enabled:
        for district in pp7.districts:
            surveyed = {
                roles[r].sector
                for e in spec.employers
                if e.district == district
                for r in e.survey_roles
                if r in roles
            }
            missing = set(pp7.sectors) - surveyed
            if missing:
                problems.append(
                    f"PP7: no employer in {district} surveys for sector(s) {sorted(missing)}"
                )
    return problems


def _cross_reference_problems(spec: WorldSpec) -> list[str]:
    problems: list[str] = []
    roles = {r.code: r for r in spec.roles}
    for course in spec.courses:
        primary = roles.get(course.primary_role)
        if primary is not None and primary.sector != course.sector:
            problems.append(
                f"course {course.code} is in sector {course.sector} but its primary role "
                f"{primary.code} is in {primary.sector}"
            )
        if course.type not in spec.details.candidate_education:
            problems.append(
                f"details.candidate_education has no entry for course type {course.type}"
            )
    for employer in spec.employers:
        posted = spec.posting_schedule.get(employer.district, {})
        for role in employer.survey_roles:
            if role not in posted:
                problems.append(
                    f"employer {employer.code} surveys for {role}, but posting_schedule has no "
                    f"{role} ads in {employer.district}"
                )
    years = sorted({year for i in spec.institutes for o in i.offerings for year in o.cohorts})
    latest = years[-1] if years else None
    for institute in spec.institutes:
        for offering in institute.offerings:
            if latest and latest not in offering.cohorts:
                problems.append(
                    f"institute {institute.code} {offering.course} has no {latest} cohort "
                    "(every offering must run in the latest academic year)"
                )
    return problems
