"""Deterministic synthetic ("demo") dataset generator (docs/SYNTHETIC_DATA_SPEC.md).

    dataset = generate(config, spec)          # seed from config/synthetic.yaml (or SYNTH_SEED)
    dataset = generate(config, spec, seed=7)  # another seed: other details, same patterns

The result maps table name -> rows (plain dicts, one key per column), in load order.
Rules that keep it honest and reproducible:

* Every synthetic row has is_synthetic = true, a Y-source ID, the seed in source_ref, a
  fixed fetched_at (the spec's generated_at) and a "SYNTHETIC ..." license note.
* Official codes are never set; institutes and employers are fictional ("Example ...").
* The COUNTS that make the planted patterns come from the spec. Randomness (seeded) only
  picks details, and every random stream is keyed by what it describes (e.g. seed +
  "postings" + district + role + quarter), so changing one part of the spec does not
  reshuffle the rest.
* No clock, no dict/set ordering surprises: the same seed + spec give byte-identical exports.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Any, TypeVar

from app.config import ProductConfig
from app.config.base import quarter_index
from app.jobs.dedupe import posting_dedupe_key
from app.models.enums import (
    EnrollmentStatus,
    EvidenceKind,
    ExtractionMethod,
    ExtractionStatus,
    Language,
    MappingReviewStatus,
    MatchDecision,
    PlacementType,
    Proficiency,
    SalaryPeriod,
    SkillVerification,
    Willingness,
)
from app.nlp.text import normalize_text
from app.synthetic.ids import synthetic_id
from app.synthetic.spec import CourseSpec, EmployerSpec, RoleSpec, WorldSpec
from app.synthetic.tables import BY_NAME, REFERENCE_TABLES, SYNTHETIC_TABLES, columns
from app.synthetic.timeline import (
    academic_year_start,
    quarter_end,
    quarter_of,
    quarter_range,
    quarter_start,
)

# Bump when the generator's logic changes (recorded in the export manifest).
GENERATOR_VERSION = "2"

IST = timezone(timedelta(hours=5, minutes=30))
# Postings from the same employer, title and district in the same ISO week count as one
# duplicate (job_posting.dedupe_key). The generator never produces such duplicates.
_MAX_EMPLOYER_RETRIES = 200

Row = dict[str, Any]
Dataset = dict[str, list[Row]]
T = TypeVar("T")


class GenerationError(Exception):
    """The spec cannot be turned into a valid dataset (e.g. duplicate postings)."""


# --------------------------------------------------------------------------- helpers
def round_half_up(value: Decimal | Fraction | float) -> int:
    """Exact rounding (0.5 -> 1). Shares are taken from the YAML text, not binary floats."""
    if isinstance(value, float):
        value = Decimal(str(value))
    if isinstance(value, Fraction):
        value = Decimal(value.numerator) / Decimal(value.denominator)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def share_of(count: int, share: float) -> int:
    """round_half_up(count x share), computed exactly (0.15 x 43 = 6.45 -> 6)."""
    return round_half_up(Decimal(str(share)) * count)


def allocate(total: int, shares: Mapping[T, float]) -> dict[T, int]:
    """Split `total` by shares with the largest-remainder method (counts add up to total)."""
    exact = {key: Decimal(str(share)) * total for key, share in shares.items()}
    counts = {key: int(value) for key, value in exact.items()}
    remaining = total - sum(counts.values())
    by_remainder = sorted(exact, key=lambda key: exact[key] - counts[key], reverse=True)
    for key in by_remainder[:remaining]:
        counts[key] += 1
    return counts


def pick(rng: random.Random, weights: Mapping[T, float]) -> T:
    """Weighted choice in the mapping's own order (deterministic for a given rng)."""
    point = rng.random() * sum(weights.values())
    cumulative = 0.0
    for key, weight in weights.items():
        cumulative += weight
        if point < cumulative:
            return key
    return next(reversed(list(weights)))


def round_to_500(value: float) -> Decimal:
    return Decimal(round_half_up(Decimal(str(value)) / 500) * 500)


def role_aliases(role: RoleSpec) -> list[str]:
    """The role's aliases plus its job-ad titles in every language (each once, in order),
    so role matching recognises titles such as 'ईव्ही सर्व्हिस टेक्निशियन'."""
    seen = {normalize_text(role.title)}
    aliases = []
    for text in [*role.aliases, *(t for titles in role.titles.values() for t in titles)]:
        if (key := normalize_text(text)) and key not in seen:
            seen.add(key)
            aliases.append(text)
    return aliases


def reference_rows(config: ProductConfig) -> Dataset:
    """Sector and district rows from config (not synthetic; the loader creates them only if
    they are missing). Official district codes are never set here."""
    sectors = [
        {
            "id": synthetic_id("sector", sector.code),
            "code": sector.code,
            "name": sector.name,
            "ssc_name": None,
            "description": sector.description,
            "source": "CONFIG",
            "source_ref": "config/sectors.yaml",
            "fetched_at": None,
            "license_note": None,
            "is_synthetic": False,
        }
        for sector in config.sectors.sectors
    ]
    districts = [
        {
            "id": synthetic_id("district", district.code),
            "code": district.code,
            "name": district.name,
            "state_name": config.scope.state,
            "aliases": list(district.aliases),
            "official_code": None,
            "official_code_scheme": None,
            "official_code_verified": False,
            "source": "CONFIG",
            "source_ref": "config/scope.yaml",
            "fetched_at": None,
            "license_note": None,
            "is_synthetic": False,
        }
        for district in config.scope.districts
    ]
    return {"sector": sectors, "district": districts}


# --------------------------------------------------------------------------- generator
def generate(config: ProductConfig, spec: WorldSpec, seed: int | None = None) -> Dataset:
    """Build the whole synthetic dataset. Pure function: no database, no clock."""
    builder = _Builder(config, spec, config.synthetic.seed if seed is None else seed)
    builder.build()
    return builder.finish()


class _Builder:
    def __init__(self, config: ProductConfig, spec: WorldSpec, seed: int) -> None:
        self.config = config
        self.spec = spec
        self.seed = seed
        history = config.synthetic.history
        self.quarters = quarter_range(history.start_quarter, history.end_quarter)
        self.tables: Dataset = {name: [] for name in (*REFERENCE_TABLES, *BY_NAME)}
        for name, rows in reference_rows(config).items():
            self.tables[name] = rows

        self.skills = {s.code: s for s in spec.skills}
        self.roles = {r.code: r for r in spec.roles}
        self.courses = {c.code: c for c in spec.courses}
        # Demo employers that hire for a role in a district (they survey for that role).
        self.hirers: dict[tuple[str, str], list[EmployerSpec]] = {}
        for employer in spec.employers:
            for role in employer.survey_roles:
                self.hirers.setdefault((employer.district, role), []).append(employer)
        # Placements already given to each demo employer: (employer, year, kind) -> count
        self.hired: dict[tuple[str, str, str], int] = {}

    # -------- ids, randomness, provenance
    def rng(self, *parts: object) -> random.Random:
        """An independent random stream per topic, e.g. rng("postings", "MH-PUNE", ...)."""
        return random.Random(f"{self.seed}:" + ":".join(str(p) for p in parts))

    @staticmethod
    def sector_id(code: str) -> Any:
        return synthetic_id("sector", code)

    @staticmethod
    def district_id(code: str) -> Any:
        return synthetic_id("district", code)

    @staticmethod
    def skill_id(code: str) -> Any:
        return synthetic_id("skill", code)

    @staticmethod
    def role_id(code: str) -> Any:
        return synthetic_id("job_role", code)

    def provenance(self, table: str) -> Row:
        info = BY_NAME[table]
        if not info.has_source:
            return {"is_synthetic": True}
        source = getattr(self.config.synthetic.source_ids, info.dataset)
        return {
            "source": source,
            "source_ref": f"KaushalSetu synthetic generator v{GENERATOR_VERSION}, seed {self.seed}",
            "fetched_at": self.spec.generated_at,
            "license_note": self.spec.license_note,
            "is_synthetic": True,
        }

    def add(self, table: str, **values: Any) -> Row:
        row = {**values, **self.provenance(table)}
        self.tables[table].append(row)
        return row

    def phrase(self, skill_code: str, language: Language, rng: random.Random) -> str:
        """How a job ad or survey names a skill: its name or an alias in that language."""
        skill = self.skills[skill_code]
        if language == Language.EN:
            return rng.choice([skill.name, *skill.aliases.get(Language.EN, [])])
        local = skill.aliases.get(language, [])
        return rng.choice(local) if local else skill.name

    def last_day(self, quarter: str) -> date:
        return min(quarter_end(quarter), self.spec.as_of)

    def random_day(self, quarter: str, rng: random.Random) -> date:
        start = quarter_start(quarter)
        return start + timedelta(days=rng.randrange((self.last_day(quarter) - start).days + 1))

    # -------- build everything
    def build(self) -> None:
        self.vocabulary()
        self.institutes()
        self.employers()
        self.events()
        self.consultations()
        self.surveys()
        self.postings()
        self.learners()

    def finish(self) -> Dataset:
        """Order every row's keys like the table's columns and check nothing is missing."""
        dataset: Dataset = {}
        for name in (*REFERENCE_TABLES, *(t.name for t in SYNTHETIC_TABLES)):
            wanted = columns(name)
            ordered = []
            for row in self.tables[name]:
                if set(row) != set(wanted):
                    missing, extra = set(wanted) - set(row), set(row) - set(wanted)
                    raise GenerationError(f"{name}: missing {missing}, unexpected {extra}")
                ordered.append({column: row[column] for column in wanted})
            dataset[name] = ordered
        return dataset

    # -------- Y13 vocabulary, Y12 equipment
    def vocabulary(self) -> None:
        spec = self.spec
        for skill in spec.skills:
            self.add(
                "skill",
                id=self.skill_id(skill.code),
                code=skill.code,
                name=skill.name,
                skill_type=skill.type.value,
                description=skill.description,
            )
            for language, aliases in skill.aliases.items():
                for alias in aliases:
                    normalized = normalize_text(alias)
                    self.add(
                        "skill_alias",
                        id=synthetic_id("skill_alias", language.value, normalized),
                        skill_id=self.skill_id(skill.code),
                        alias=alias,
                        alias_normalized=normalized,
                        language=language.value,
                    )
        for role in spec.roles:
            self.add(
                "job_role",
                id=self.role_id(role.code),
                code=role.code,
                title=role.title,
                sector_id=self.sector_id(role.sector),
                nsqf_level=None,  # official level not verified: never invented
                aliases=role_aliases(role),
                description=role.description,
                official_code=None,
                official_code_scheme=None,
                official_code_verified=False,
            )
            for link in role.skills:
                self.add(
                    "role_skill",
                    role_id=self.role_id(role.code),
                    skill_id=self.skill_id(link.skill),
                    importance=link.importance,
                    required_band=link.band,
                )
        for step in spec.career_steps:
            self.add(
                "role_edge",
                id=synthetic_id("role_edge", step.from_role, step.to_role),
                from_role_id=self.role_id(step.from_role),
                to_role_id=self.role_id(step.to_role),
                edge_type=step.type.value,
                typical_training_hours=step.training_hours,
                note=step.note,
            )
        for course in spec.courses:
            course_id = synthetic_id("course", course.code)
            self.add(
                "course",
                id=course_id,
                code=course.code,
                name=course.name,
                course_type=course.type.value,
                sector_id=self.sector_id(course.sector),
                qualification_pack_id=None,
                duration_hours=course.duration_hours,  # None = not modelled (ITI trades)
                nsqf_level=None,
                syllabus_version=course.syllabus_version,
                official_code=None,
                official_code_scheme=None,
                official_code_verified=False,
            )
            for sequence, module in enumerate(course.modules, start=1):
                module_id = synthetic_id("course_module", course.code, sequence)
                self.add(
                    "course_module",
                    id=module_id,
                    course_id=course_id,
                    sequence=sequence,
                    title=module.title,
                    hours=Decimal(module.hours),
                    is_elective=False,
                    description=None,
                )
                for skill, band in module.skills.items():
                    self.add(
                        "module_skill",
                        module_id=module_id,
                        skill_id=self.skill_id(skill),
                        band_taught=band,
                        review_status=MappingReviewStatus.APPROVED.value,
                    )
            for role, primary in [(course.primary_role, True)] + [
                (r, False) for r in course.secondary_roles
            ]:
                self.add(
                    "course_role",
                    course_id=course_id,
                    role_id=self.role_id(role),
                    is_primary=primary,
                )
        for item in spec.equipment:
            equipment_id = synthetic_id("equipment", item.code)
            self.add(
                "equipment",
                id=equipment_id,
                code=item.code,
                name=item.name,
                category=item.category,
                indicative_cost_inr=Decimal(item.cost_inr),
                cost_is_estimate=True,
            )
            for skill, quantity in item.skills.items():
                self.add(
                    "skill_equipment",
                    skill_id=self.skill_id(skill),
                    equipment_id=equipment_id,
                    qty_per_batch=quantity,
                )

    # -------- Y14 institutes, Y05 offerings, Y06 trainers, Y07 inventory
    def institutes(self) -> None:
        for institute in self.spec.institutes:
            institute_id = synthetic_id("institute", institute.code)
            self.add(
                "institute",
                id=institute_id,
                code=institute.code,
                name=institute.name,
                institute_type=institute.type.value,
                ownership=institute.ownership.value,
                district_id=self.district_id(institute.district),
                official_code=None,
                official_code_scheme=None,
                official_code_verified=False,
            )
            for offering in institute.offerings:
                course_id = synthetic_id("course", offering.course)
                for year, cohort in sorted(offering.cohorts.items()):
                    completed = share_of(cohort.filled, cohort.completion)
                    self.add(
                        "course_offering",
                        id=synthetic_id("course_offering", institute.code, offering.course, year),
                        institute_id=institute_id,
                        course_id=course_id,
                        academic_year=year,
                        seats=offering.seats,
                        seats_filled=cohort.filled,
                        # The realised rate, so seats_filled x rate = completers.
                        completion_rate=(
                            round(completed / cohort.filled, 4) if cohort.filled else None
                        ),
                    )

            # Trainers: `trainers_per_offering` per course, each able to teach the course's
            # skills at the band the course teaches them. Pseudonyms only (no personal data).
            number = 0
            taught: dict[str, int] = {}
            for offering in institute.offerings:
                course = self.courses[offering.course]
                for skill, band in course.taught_bands.items():
                    taught[skill] = max(band, taught.get(skill, 0))
                for _ in range(course.trainers_per_offering):
                    number += 1
                    trainer_id = synthetic_id("trainer", institute.code, number)
                    self.add(
                        "trainer",
                        id=trainer_id,
                        institute_id=institute_id,
                        pseudonym=f"T-{number:02d}",
                        certifications=list(course.trainer_certifications),
                        is_active=True,
                    )
                    for skill, band in course.taught_bands.items():
                        self.add(
                            "trainer_skill",
                            trainer_id=trainer_id,
                            skill_id=self.skill_id(skill),
                            band=band,
                        )

            # Inventory: the equipment for skills the institute teaches (nothing else, so
            # an institute without EV courses owns no EV kit).
            for item in self.spec.equipment:
                needed = [qty for skill, qty in item.skills.items() if skill in taught]
                if not needed:
                    continue
                rng = self.rng("inventory", institute.code, item.code)
                self.add(
                    "institute_equipment",
                    institute_id=institute_id,
                    equipment_id=synthetic_id("equipment", item.code),
                    quantity=max(needed),
                    condition=pick(rng, self.spec.details.equipment_condition).value,
                )

    # -------- Y15 employers, Y04 events, Y03 consultations
    def employers(self) -> None:
        for employer in self.spec.employers:
            self.add(
                "employer",
                id=synthetic_id("employer", employer.code),
                code=employer.code,
                name=employer.name,
                sector_id=self.sector_id(employer.sector),
                district_id=self.district_id(employer.district),
                size=employer.size.value,
                is_msme_registered=employer.msme,
            )

    def events(self) -> None:
        for event in self.spec.sector_events:
            self.add(
                "sector_event",
                id=synthetic_id("sector_event", event.key),
                sector_id=self.sector_id(event.sector),
                district_id=self.district_id(event.district),
                event_type=event.type.value,
                title=event.title,
                description=event.description,
                expected_jobs=event.expected_jobs,
                announced_on=event.announced_on,
                announced_quarter=quarter_of(event.announced_on),
                realization_factor=event.realization_factor,
                citation_url=None,  # hypothetical: there is nothing to cite
                is_simulated=True,
            )

    def consultations(self) -> None:
        for consultation in self.spec.consultations:
            consultation_id = synthetic_id("consultation", consultation.key)
            self.add(
                "consultation",
                id=consultation_id,
                title=consultation.title,
                held_on=consultation.held_on,
                district_id=self.district_id(consultation.district),
                sector_id=self.sector_id(consultation.sector),
                participant_type=consultation.participant.value,
                notes=consultation.notes,
                consent_to_quote=False,
            )
            for number, insight in enumerate(consultation.insights, start=1):
                self.add(
                    "consultation_insight",
                    id=synthetic_id("consultation_insight", consultation.key, number),
                    consultation_id=consultation_id,
                    skill_id=self.skill_id(insight.skill) if insight.skill else None,
                    insight_type=insight.type.value,
                    summary=insight.summary,
                    quote=None,
                    quote_approved=False,
                    extracted_by=ExtractionMethod.GENERATED.value,
                    review_status=MappingReviewStatus.APPROVED.value,
                )

    # -------- Y02 employer survey
    def survey_headcount(self, first: int, last: int, index: int) -> int:
        """Straight line from the first to the last quarter's headcount."""
        steps = len(self.quarters) - 1
        if steps == 0:
            return last
        return round_half_up(Fraction(first) + Fraction(last - first) * index / steps)

    def active_survey_skills(self, employer: EmployerSpec, quarter: str) -> list[str]:
        return [
            skill
            for skill, first in employer.survey_skills.items()
            if first is None or quarter_index(quarter) >= quarter_index(first)
        ]

    def surveys(self) -> None:
        settings = self.spec.postings
        for employer in self.spec.employers:
            language = employer.language
            for index, quarter in enumerate(self.quarters):
                rng = self.rng("survey", employer.code, quarter)
                roles_json = []
                for role_code, (first, last) in employer.survey_roles.items():
                    count = self.survey_headcount(first, last, index)
                    if count <= 0:
                        continue
                    role = self.roles[role_code]
                    roles_json.append(
                        {
                            "role_id": str(self.role_id(role_code)),
                            "role_text": role.titles.get(language, role.titles[Language.EN])[0],
                            "count": count,
                            "timeframe_months": 12,
                        }
                    )
                skills = self.active_survey_skills(employer, quarter)
                phrases = [self.phrase(skill, language, rng) for skill in skills]
                skills_json = [
                    {"skill_id": str(self.skill_id(skill)), "text": text}
                    for skill, text in zip(skills, phrases, strict=True)
                ]
                day = self.random_day(quarter, rng)
                submitted = datetime.combine(
                    day, time(rng.randint(9, 18), rng.choice([0, 15, 30, 45])), tzinfo=IST
                )
                willing = employer.apprenticeship
                self.add(
                    "employer_survey_response",
                    id=synthetic_id("employer_survey_response", employer.code, quarter),
                    employer_id=synthetic_id("employer", employer.code),
                    district_id=self.district_id(employer.district),
                    business_type=employer.business_type,
                    business_size=employer.size.value,
                    channel=pick(rng, self.spec.details.survey_channels).value,
                    language=language.value,
                    consent_given=True,
                    submitted_at=submitted,
                    roles_json=roles_json,
                    skills_json=skills_json,
                    hardest_skills_text=settings.hardest_skills_text[language].format(
                        skills=", ".join(phrases)
                    ),
                    apprenticeship_willingness=willing.value,
                    apprentices_possible=employer.apprentices_possible,
                    recontact_consent=willing != Willingness.NO,
                )

    # -------- Y01 job postings (+ ground-truth posting_role / posting_skill links)
    def postings(self) -> None:
        seen: set[tuple[str, str, str, str]] = set()
        for district, schedule in self.spec.posting_schedule.items():
            for role_code, counts in schedule.items():
                role = self.roles[role_code]
                for quarter, count in zip(self.quarters, counts, strict=True):
                    self.postings_for(district, role, quarter, count, seen)

    def postings_for(
        self,
        district: str,
        role: RoleSpec,
        quarter: str,
        count: int,
        seen: set[tuple[str, str, str, str]],
    ) -> None:
        spec = self.spec
        settings = spec.postings
        place = spec.districts[district]
        rng = self.rng("postings", district, role.code, quarter)
        # Exact number of ads naming each optional skill (so mention counts are fixed).
        naming: dict[str, set[int]] = {}
        for link in role.skills:
            if link.posting_share < 1.0:
                naming[link.skill] = set(
                    rng.sample(range(count), share_of(count, link.posting_share))
                )
        hirers = self.hirers.get((district, role.code), [])
        # A demo employer posts at most ceil(headcount it asks for / 4) + slack ads a quarter.
        index = self.quarters.index(quarter)
        caps = {}
        for employer in hirers:
            need = self.survey_headcount(*employer.survey_roles[role.code], index)
            caps[employer.code] = math.ceil(need / 4) + settings.directory_ads_slack if need else 0
        posted = dict.fromkeys(caps, 0)
        pool_name = settings.employer_pool_names[role.sector]

        for number in range(1, count + 1):
            language = pick(rng, place.posting_languages)
            title = rng.choice(role.titles.get(language, role.titles[Language.EN]))
            posted_on = self.random_day(quarter, rng)
            location = f"{rng.choice(place.areas)}, {rng.choice(place.spellings)}"
            week = "{}-W{:02d}".format(*posted_on.isocalendar()[:2])

            employer_id = employer_code = None
            open_hirers = [e for e in hirers if posted[e.code] < caps[e.code]]
            if open_hirers and rng.random() < settings.directory_employer_share:
                employer = rng.choice(open_hirers)
                employer_id, employer_name = synthetic_id("employer", employer.code), employer.name
                employer_code = employer.code
            else:
                employer_name = self.pool_employer(pool_name, rng)
            key = (normalize_text(title), normalize_text(employer_name), district, week)
            retries = 0
            while key in seen:  # never create a duplicate ad (same dedupe key)
                retries += 1
                if retries > _MAX_EMPLOYER_RETRIES:
                    raise GenerationError(
                        f"cannot place {role.code} ad #{number} in {district} {quarter} without "
                        "a duplicate; raise postings.employer_pool_size"
                    )
                employer_id, employer_code = None, None
                employer_name = self.pool_employer(pool_name, rng)
                key = (normalize_text(title), normalize_text(employer_name), district, week)
            seen.add(key)
            if employer_code is not None:
                posted[employer_code] += 1

            skill_links = [
                link
                for link in role.skills
                if link.posting_share == 1.0 or (number - 1) in naming[link.skill]
            ]
            phrases = [self.phrase(link.skill, language, rng) for link in skill_links]
            low, high = rng.choice(role.experience_years)
            salary_min = salary_max = None
            salary_text = ""
            if rng.random() < settings.salary_stated_share:
                floor = role.salary_monthly_inr.min * place.salary_factor
                ceiling = role.salary_monthly_inr.max * place.salary_factor
                salary_min = round_to_500(floor + rng.random() * (ceiling - floor) / 2)
                salary_max = max(
                    salary_min + 1000,
                    round_to_500(float(salary_min) + rng.random() * (ceiling - float(salary_min))),
                )
                salary_text = settings.salary_text[language].format(
                    low=int(salary_min), high=int(salary_max)
                )
            description = settings.text[language].format(
                title=title,
                employer=employer_name,
                location=location,
                skills=", ".join(phrases),
                experience=settings.experience_text[language].format(low=low, high=high),
            )
            if salary_text:
                description = f"{description} {salary_text}"
            posting_id = synthetic_id("job_posting", district, role.code, quarter, number)
            self.add(
                "job_posting",
                id=posting_id,
                title=title,
                description=description,
                employer_id=employer_id,
                employer_name_raw=employer_name,
                district_id=self.district_id(district),
                sector_id=self.sector_id(role.sector),
                location_raw=location,
                posted_on=posted_on,
                quarter=quarter,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_period=SalaryPeriod.MONTH.value if salary_min is not None else None,
                experience_min_years=Decimal(low),
                experience_max_years=Decimal(high),
                language=language.value,
                dedupe_key=posting_dedupe_key(title, employer_name, district, posted_on),
                # Links below are the generator's ground truth, so nothing is left to extract.
                extraction_status=ExtractionStatus.DONE.value,
                processed_at=None,
                extraction_error=None,
            )
            truth = {
                "generator": f"v{GENERATOR_VERSION}",
                "note": "ground truth of the synthetic generator",
            }
            self.add(
                "posting_role",
                posting_id=posting_id,
                role_id=self.role_id(role.code),
                confidence=1.0,
                method=ExtractionMethod.GENERATED.value,
                evidence_kind=EvidenceKind.SYNTHETIC.value,
                decision=MatchDecision.ACCEPT.value,
                evidence_text=title,
                evidence_json=truth,
            )
            for link, text in zip(skill_links, phrases, strict=True):
                self.add(
                    "posting_skill",
                    posting_id=posting_id,
                    skill_id=self.skill_id(link.skill),
                    confidence=1.0,
                    method=ExtractionMethod.GENERATED.value,
                    band=link.band,
                    matched_text=text,
                    evidence_kind=EvidenceKind.SYNTHETIC.value,
                    decision=MatchDecision.ACCEPT.value,
                    proficiency=Proficiency.UNKNOWN.value,
                    evidence_text=text,
                    evidence_json=truth,
                )

    def pool_employer(self, pool_name: str, rng: random.Random) -> str:
        """A small fictional employer, e.g. "Example EV Garage 07" (per district)."""
        return f"{pool_name} {rng.randint(1, self.spec.postings.employer_pool_size):02d}"

    def employer_with_room(
        self,
        hirers: list[EmployerSpec],
        role_code: str,
        year: str,
        placement_type: PlacementType,
        rng: random.Random,
    ) -> EmployerSpec | None:
        """A demo employer that still has room this academic year: apprentices only where
        the employer takes apprentices (up to apprentices_possible), wage hires up to the
        headcount it asks for in the survey. None = placed with an employer outside the
        demo directory."""
        kind = placement_type.value
        room = []
        for employer in hirers:
            if placement_type == PlacementType.APPRENTICESHIP:
                willing = employer.apprenticeship != Willingness.NO
                limit = employer.apprentices_possible if willing else 0
            else:
                limit = max(employer.survey_roles[role_code])
            if self.hired.get((employer.code, year, kind), 0) < limit:
                room.append(employer)
        if not room:
            return None
        chosen = rng.choice(room)
        key = (chosen.code, year, kind)
        self.hired[key] = self.hired.get(key, 0) + 1
        return chosen

    # -------- Y08 candidates, Y09 enrollments, Y10 outcomes, Y11 ratings
    def learners(self) -> None:
        for institute in self.spec.institutes:
            for offering in institute.offerings:
                course = self.courses[offering.course]
                for year, cohort in sorted(offering.cohorts.items()):
                    # Stable per cohort: editing one cohort never renames other people.
                    prefix = (
                        f"C-{institute.code.removeprefix('EX-')}-"
                        f"{course.code.removeprefix('demo-')}-{year[:4]}"
                    )
                    pseudonyms = [f"{prefix}-{k:03d}" for k in range(1, cohort.filled + 1)]
                    self.cohort(
                        institute.code, institute.district, course, year, cohort, pseudonyms
                    )

    def cohort(
        self,
        institute_code: str,
        district: str,
        course: CourseSpec,
        year: str,
        cohort: Any,
        pseudonyms: Sequence[str],
    ) -> None:
        spec, details, outcomes = self.spec, self.spec.details, self.spec.outcomes
        rng = self.rng("cohort", institute_code, course.code, year)
        offering_key = f"{institute_code}|{course.code}|{year}"
        offering_id = synthetic_id("course_offering", institute_code, course.code, year)
        start = academic_year_start(year)
        taught = course.taught_bands
        first_module = course.modules[0].skills
        role = self.roles[course.primary_role]

        n_completed = share_of(cohort.filled, cohort.completion)
        completers = set(rng.sample(range(cohort.filled), n_completed))
        finished: list[tuple[str, date]] = []  # (pseudonym, completed_on)

        for index, pseudonym in enumerate(pseudonyms):
            candidate_id = synthetic_id("candidate", pseudonym)
            languages = [
                language.value
                for language, chance in details.candidate_languages.items()
                if rng.random() < chance
            ] or [Language.MR.value]
            self.add(
                "candidate",
                id=candidate_id,
                pseudonym=pseudonym,
                district_id=self.district_id(district),
                education_level=pick(rng, details.candidate_education[course.type]).value,
                languages=languages,
                consent_json={
                    "analytics": True,
                    "contact_by_employers": rng.random() < details.contact_consent_share,
                },
            )
            if course.delivery == "annual":
                # Cohorts are keyed by the academic year in which they COMPLETE; a 2-year
                # ITI trade cohort enrolled one year earlier.
                years_before = (course.programme_years or 1) - 1
                enrolled_on = date(start - years_before, 8, 1) + timedelta(days=rng.randrange(31))
                completed_on = date(start + 1, 7, 15) + timedelta(days=rng.randrange(17))
            else:
                duration = course.duration_days or 0
                latest = (date(start + 1, 7, 31) - date(start, 8, 1)).days - duration - 7
                enrolled_on = date(start, 8, 1) + timedelta(days=rng.randrange(latest + 1))
                completed_on = enrolled_on + timedelta(days=duration + rng.randrange(8))
            done = index in completers
            self.add(
                "enrollment",
                id=synthetic_id("enrollment", pseudonym, offering_key),
                candidate_id=candidate_id,
                course_offering_id=offering_id,
                status=(EnrollmentStatus.COMPLETED if done else EnrollmentStatus.DROPPED).value,
                enrolled_on=enrolled_on,
                completed_on=completed_on if done else None,
            )
            skills = taught if done else {skill: 1 for skill in first_module}
            for skill, band in skills.items():
                self.add(
                    "candidate_skill",
                    candidate_id=candidate_id,
                    skill_id=self.skill_id(skill),
                    band=band,
                    verified_by=(
                        SkillVerification.CERTIFICATE if done else SkillVerification.SELF
                    ).value,
                )
            if done:
                finished.append((pseudonym, completed_on))

        # Outcomes: exact numbers placed / related / retained; the seed picks who.
        n_placed = share_of(len(finished), cohort.placement)
        placed = sorted(rng.sample(range(len(finished)), n_placed))
        types: list[PlacementType] = []
        for placement_type, count in allocate(n_placed, course.placement_types).items():
            types.extend([placement_type] * count)
        rng.shuffle(types)
        related = set(rng.sample(placed, share_of(n_placed, outcomes.related_to_training_share)))
        delay = details.placement_delay_days
        placed_on: dict[int, date] = {}
        for k in placed:
            completed_on = finished[k][1]
            upper = min(delay.max, (spec.as_of - completed_on).days)
            placed_on[k] = completed_on + timedelta(days=rng.randint(min(delay.min, upper), upper))
        # Retention is known only 6 months after placement.
        known = [k for k in placed if placed_on[k] + timedelta(days=182) <= spec.as_of]
        retention = (
            cohort.retention_6m if cohort.retention_6m is not None else outcomes.retention_6m
        )
        retained = set(rng.sample(known, share_of(len(known), retention)))
        hirers = self.hirers.get((district, role.code), [])
        rating_mean = outcomes.rating_mean.get(course.code, outcomes.rating_mean["default"])
        factor = spec.districts[district].salary_factor

        for k, (pseudonym, completed_on) in enumerate(finished):
            outcome_id = synthetic_id("placement_outcome", pseudonym, offering_key)
            follow_up_done = completed_on + timedelta(days=182) <= spec.as_of
            if k not in placed:
                self.add(
                    "placement_outcome",
                    id=outcome_id,
                    enrollment_id=synthetic_id("enrollment", pseudonym, offering_key),
                    placed=False,
                    placement_type=None,
                    employer_id=None,
                    role_id=None,
                    salary_monthly_inr=None,
                    placed_on=None,
                    retained_6m=None,
                    related_to_training=None,
                    verified=follow_up_done,
                )
                continue
            placement_type = types[placed.index(k)]
            is_related = k in related
            employer = None
            if (
                placement_type != PlacementType.SELF_EMPLOYED
                and is_related
                and hirers
                and rng.random() < outcomes.employer_link_share
            ):
                employer = self.employer_with_room(hirers, role.code, year, placement_type, rng)
            salary = None
            if placement_type == PlacementType.WAGE:
                low, high = role.salary_monthly_inr.min, role.salary_monthly_inr.max
                salary = round_to_500((low + rng.random() * (high - low)) * factor)
            self.add(
                "placement_outcome",
                id=outcome_id,
                enrollment_id=synthetic_id("enrollment", pseudonym, offering_key),
                placed=True,
                placement_type=placement_type.value,
                employer_id=synthetic_id("employer", employer.code) if employer else None,
                role_id=self.role_id(role.code) if is_related else None,
                salary_monthly_inr=salary,
                placed_on=placed_on[k],
                retained_6m=(k in retained) if k in known else None,
                related_to_training=is_related,
                verified=follow_up_done,
            )
            rated_after = placed_on[k] + timedelta(days=90)
            if employer is not None and rated_after <= spec.as_of:
                rated_on = min(rated_after + timedelta(days=rng.randrange(31)), spec.as_of)
                needs = set(self.active_survey_skills(employer, quarter_of(rated_on)))
                self.add(
                    "employer_rating",
                    id=synthetic_id("employer_rating", pseudonym, offering_key),
                    placement_outcome_id=outcome_id,
                    employer_id=synthetic_id("employer", employer.code),
                    rating=min(5, max(1, round_half_up(rating_mean + rng.uniform(-1, 1)))),
                    skill_feedback={
                        "strengths": sorted(needs & set(taught)),
                        "needs_improvement": sorted(needs - set(taught)),
                    },
                    rated_on=rated_on,
                )
