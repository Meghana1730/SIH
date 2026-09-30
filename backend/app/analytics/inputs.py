"""Everything the demand/supply/mismatch engine reads, loaded once from the database.

Only evidence that may count as demand is used:
* job postings -> role / skill links with decision 'accept' and evidence_kind OBSERVED or
  SYNTHETIC (generator ground truth). INFERRED links (implied by a role) and 'review' links
  never count as demand.
* employer survey answers, sector events, course offerings, enrollments and placements.
Every record keeps its is_synthetic flag, so every result can say how much of it is demo data.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ProductConfig
from app.models import (
    Course,
    CourseModule,
    CourseOffering,
    CourseRole,
    District,
    EmployerSurveyResponse,
    Enrollment,
    Institute,
    JobPosting,
    JobRole,
    ModuleSkill,
    PlacementOutcome,
    PostingRole,
    PostingSkill,
    Sector,
    SectorEvent,
    Skill,
)
from app.models.enums import EnrollmentStatus, EvidenceKind, MatchDecision
from app.synthetic.timeline import quarter_of, quarter_range

IST = timezone(timedelta(hours=5, minutes=30))
COUNTED = (EvidenceKind.OBSERVED.value, EvidenceKind.SYNTHETIC.value)


@dataclass(frozen=True)
class RoleInfo:
    id: uuid.UUID
    code: str
    title: str
    sector: str


@dataclass(frozen=True)
class SurveyAnswer:
    id: uuid.UUID
    employer_id: uuid.UUID | None
    district_id: uuid.UUID
    quarter: str
    headcount: dict[uuid.UUID, int]  # role id -> people needed
    skills: frozenset[uuid.UUID]
    is_synthetic: bool


@dataclass(frozen=True)
class EventInfo:
    id: uuid.UUID
    title: str
    sector: str
    district_id: uuid.UUID | None
    announced_quarter: str
    expected_jobs: int
    realization_factor: float | None
    is_synthetic: bool
    is_simulated: bool


@dataclass(frozen=True)
class OfferingInfo:
    id: uuid.UUID
    institute_id: uuid.UUID
    institute_code: str
    institute_name: str
    course_id: uuid.UUID
    course_code: str
    course_name: str
    district_id: uuid.UUID
    academic_year: str
    seats: int
    seats_filled: int | None
    completion_rate: float | None
    primary_role: uuid.UUID | None
    other_roles: tuple[uuid.UUID, ...]
    skills: dict[uuid.UUID, int]  # skill -> highest band taught
    is_synthetic: bool


@dataclass(frozen=True)
class Completion:
    offering_id: uuid.UUID
    completed_on: date
    placed_role: uuid.UUID | None  # the role the person was placed in (None = not placed / other)
    placed: bool
    is_synthetic: bool


@dataclass
class Counts:
    total: int = 0
    synthetic: int = 0

    def add(self, synthetic: bool) -> None:
        self.total += 1
        self.synthetic += int(synthetic)


@dataclass
class Inputs:
    quarters: list[str]
    districts: dict[uuid.UUID, tuple[str, str]]  # id -> (code, name)
    roles: dict[uuid.UUID, RoleInfo]
    skills: dict[uuid.UUID, tuple[str, str]]  # id -> (code, name)
    role_postings: dict[tuple[uuid.UUID, uuid.UUID, str], Counts] = field(default_factory=dict)
    skill_mentions: dict[tuple[uuid.UUID, uuid.UUID, str], Counts] = field(default_factory=dict)
    posting_districts: set[uuid.UUID] = field(default_factory=set)
    surveys: list[SurveyAnswer] = field(default_factory=list)
    events: list[EventInfo] = field(default_factory=list)
    offerings: list[OfferingInfo] = field(default_factory=list)
    completions: list[Completion] = field(default_factory=list)

    def district_code(self, district_id: uuid.UUID) -> str:
        return self.districts[district_id][0]

    def sector_roles(self, sector: str) -> list[RoleInfo]:
        return sorted((r for r in self.roles.values() if r.sector == sector), key=lambda r: r.code)


def load_inputs(db: Session, config: ProductConfig) -> Inputs:
    history = config.synthetic.history
    codes = config.scope.district_codes
    districts = {
        d.id: (d.code, d.name) for d in db.scalars(select(District).where(District.code.in_(codes)))
    }
    roles = {
        r.id: RoleInfo(r.id, r.code, r.title, sector)
        for r, sector in db.execute(
            select(JobRole, Sector.code).join(Sector, Sector.id == JobRole.sector_id)
        )
    }
    skills = {s.id: (s.code, s.name) for s in db.scalars(select(Skill))}
    inputs = Inputs(
        quarter_range(history.start_quarter, history.end_quarter), districts, roles, skills
    )

    counted = (PostingRole.decision == MatchDecision.ACCEPT.value) & PostingRole.evidence_kind.in_(
        COUNTED
    )
    for role_id, district_id, quarter, synthetic in db.execute(
        select(
            PostingRole.role_id, JobPosting.district_id, JobPosting.quarter, JobPosting.is_synthetic
        )
        .join(JobPosting, JobPosting.id == PostingRole.posting_id)
        .where(counted, JobPosting.district_id.in_(districts))
    ):
        inputs.role_postings.setdefault((role_id, district_id, quarter), Counts()).add(synthetic)
    inputs.posting_districts = {
        d
        for (d,) in db.execute(
            select(JobPosting.district_id).where(JobPosting.district_id.in_(districts)).distinct()
        )
    }
    counted = (
        PostingSkill.decision == MatchDecision.ACCEPT.value
    ) & PostingSkill.evidence_kind.in_(COUNTED)
    for skill_id, district_id, quarter, synthetic in db.execute(
        select(
            PostingSkill.skill_id,
            JobPosting.district_id,
            JobPosting.quarter,
            JobPosting.is_synthetic,
        )
        .join(JobPosting, JobPosting.id == PostingSkill.posting_id)
        .where(counted, JobPosting.district_id.in_(districts))
    ):
        inputs.skill_mentions.setdefault((skill_id, district_id, quarter), Counts()).add(synthetic)

    for r in db.scalars(
        select(EmployerSurveyResponse).where(EmployerSurveyResponse.district_id.in_(districts))
    ):
        headcount: dict[uuid.UUID, int] = defaultdict(int)
        for need in r.roles_json or []:
            try:
                role_id = uuid.UUID(str(need.get("role_id")))
            except ValueError:
                continue  # free-text roles are not mapped yet
            if role_id in roles and isinstance(need.get("count"), int) and need["count"] > 0:
                headcount[role_id] += need["count"]
        skills_named = set()
        for named in r.skills_json or []:
            try:
                skills_named.add(uuid.UUID(str(named.get("skill_id"))))
            except ValueError:
                continue
        quarter = quarter_of(r.submitted_at.astimezone(IST).date())
        inputs.surveys.append(
            SurveyAnswer(
                r.id,
                r.employer_id,
                r.district_id,
                quarter,
                dict(headcount),
                frozenset(skills_named),
                r.is_synthetic,
            )
        )

    for event, sector in db.execute(
        select(SectorEvent, Sector.code).join(Sector, Sector.id == SectorEvent.sector_id)
    ):
        inputs.events.append(
            EventInfo(
                event.id,
                event.title,
                sector,
                event.district_id,
                event.announced_quarter,
                event.expected_jobs or 0,
                event.realization_factor,
                event.is_synthetic,
                event.is_simulated,
            )
        )

    links: dict[uuid.UUID, list[tuple[uuid.UUID, bool]]] = defaultdict(list)
    for course_id, role_id, primary in db.execute(
        select(CourseRole.course_id, CourseRole.role_id, CourseRole.is_primary)
    ):
        links[course_id].append((role_id, primary))
    taught: dict[uuid.UUID, dict[uuid.UUID, int]] = defaultdict(dict)
    for course_id, skill_id, band in db.execute(
        select(CourseModule.course_id, ModuleSkill.skill_id, ModuleSkill.band_taught).join(
            CourseModule, CourseModule.id == ModuleSkill.module_id
        )
    ):
        taught[course_id][skill_id] = max(band, taught[course_id].get(skill_id, 0))
    for offering, institute, course in db.execute(
        select(CourseOffering, Institute, Course)
        .join(Institute, Institute.id == CourseOffering.institute_id)
        .join(Course, Course.id == CourseOffering.course_id)
        .where(Institute.district_id.in_(districts))
    ):
        roles_of = links.get(course.id, [])
        inputs.offerings.append(
            OfferingInfo(
                offering.id,
                institute.id,
                institute.code,
                institute.name,
                course.id,
                course.code,
                course.name,
                institute.district_id,
                offering.academic_year,
                offering.seats,
                offering.seats_filled,
                offering.completion_rate,
                next((r for r, primary in roles_of if primary), None),
                tuple(r for r, primary in roles_of if not primary),
                dict(taught.get(course.id, {})),
                offering.is_synthetic,
            )
        )

    offering_ids = {o.id for o in inputs.offerings}
    for enrollment, outcome in db.execute(
        select(Enrollment, PlacementOutcome)
        .outerjoin(PlacementOutcome, PlacementOutcome.enrollment_id == Enrollment.id)
        .where(
            Enrollment.status == EnrollmentStatus.COMPLETED.value,
            Enrollment.course_offering_id.in_(offering_ids),
        )
    ):
        if enrollment.completed_on is None:
            continue
        inputs.completions.append(
            Completion(
                enrollment.course_offering_id,
                enrollment.completed_on,
                outcome.role_id if outcome is not None and outcome.placed else None,
                bool(outcome is not None and outcome.placed),
                enrollment.is_synthetic,
            )
        )
    return inputs
