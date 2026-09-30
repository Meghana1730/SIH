"""Process job postings: skills -> role -> inferred skills -> proficiency -> evidence.

    intel = JobIntelligence.create(db, config)        # vocabulary, embedder, LLM (from config)
    analysis = intel.analyze(title, description)      # nothing is stored
    result = process_posting(db, intel, posting)      # stores links + review items
    batch = process_batch(db, intel, limit=100)       # PENDING postings, one savepoint each

Stored links carry evidence_kind:
  OBSERVED   found in the posting's text (quoted in evidence_text)
  INFERRED   not stated; implied by the matched role's essential skills (always 'review')
  SYNTHETIC  written by the synthetic generator (ground truth; this pipeline never changes them)
and is_synthetic copied from the posting. Links confirmed by a human (method HUMAN) are kept.
Uncertain skills and roles, and unknown skill phrases, go to the review queue.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from app.config import ProductConfig
from app.llm import LLMClient, create_llm_client
from app.models import JobPosting, PostingRole, PostingSkill, ReviewItem, Sector
from app.models.enums import (
    EvidenceKind,
    ExtractionMethod,
    ExtractionStatus,
    MatchDecision,
    ReviewItemStatus,
    ReviewKind,
)
from app.nlp.embeddings import Embedder, get_embedder
from app.nlp.job_extraction import SkillExtractor, SkillHit, UnknownPhrase
from app.nlp.role_matching import RoleHit, RoleMatcher

PIPELINE_VERSION = "job-pipeline v1"
PIPELINE_REVIEW_KINDS = (
    ReviewKind.SKILL_MAPPING.value,
    ReviewKind.NEW_SKILL.value,
    ReviewKind.ROLE_MAPPING.value,
)
KEPT_METHODS = (ExtractionMethod.HUMAN.value, ExtractionMethod.GENERATED.value)


class GroundTruthConflict(Exception):
    """The posting carries synthetic ground-truth links, which processing must not replace."""


@dataclass
class PostingAnalysis:
    skills: list[SkillHit]
    role: RoleHit | None
    unknown: list[UnknownPhrase]
    llm_calls: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def observed(self) -> list[SkillHit]:
        return [s for s in self.skills if s.evidence_kind == EvidenceKind.OBSERVED]


class JobIntelligence:
    """Everything needed to analyse postings; build once per request or batch."""

    def __init__(
        self,
        db: Session,
        config: ProductConfig,
        *,
        embedder: Embedder | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.config = config
        self.llm = llm
        self.skills = SkillExtractor(db, config, embedder=embedder, llm=llm)
        self.roles = RoleMatcher(db, config, embedder=embedder, llm=llm)
        self.skill_refs = {
            ref.id: ref for owners in self.skills.terms.values() for ref, _, _ in owners
        }
        self.sector_codes = dict(db.execute(select(Sector.id, Sector.code)).all())

    @classmethod
    def create(cls, db: Session, config: ProductConfig) -> JobIntelligence:
        """With the embedder and LLM client configured in config/llm.yaml."""
        return cls(db, config, embedder=get_embedder(config), llm=create_llm_client(config, db=db))

    @property
    def llm_calls_made(self) -> int:
        return self.llm.calls if self.llm is not None else 0

    def analyze(
        self, title: str, description: str | None, sector: str | None = None
    ) -> PostingAnalysis:
        start_calls = len(self.roles.llm_calls)
        extraction = self.skills.extract(title, description)
        observed = {h.skill.id: (h.skill.code, h.confidence) for h in extraction.hits}
        role = self.roles.match(title, description, observed, sector)
        skills = list(extraction.hits) + self._inferred(role, extraction.hits)
        return PostingAnalysis(
            skills=sorted(skills, key=_skill_order),
            role=role,
            unknown=extraction.unknown,
            llm_calls=extraction.llm_calls + self.roles.llm_calls[start_calls:],
            notes=extraction.notes,
        )

    def _inferred(self, role: RoleHit | None, observed: list[SkillHit]) -> list[SkillHit]:
        """Essential skills of an accepted role that the ad does not state (INFERRED)."""
        settings = self.config.scoring.job_extraction.inferred_skills
        if not settings.enabled or role is None or role.decision != MatchDecision.ACCEPT:
            return []
        if role.confidence < settings.min_role_confidence:
            return []
        seen = {h.skill.id for h in observed}
        cap = self.config.scoring.skill_matching.auto_accept_confidence
        hits = []
        for skill_id, importance in sorted(
            self.roles.profiles.get(role.role.id, {}).items(), key=lambda x: -x[1]
        ):
            if (
                skill_id in seen
                or importance < settings.min_importance
                or skill_id not in self.skill_refs
            ):
                continue
            confidence = min(role.confidence * importance * settings.confidence_factor, cap - 0.01)
            hits.append(
                SkillHit(
                    skill=self.skill_refs[skill_id],
                    confidence=round(confidence, 4),
                    method=ExtractionMethod.ROLE_PROFILE,
                    decision=MatchDecision.REVIEW,
                    evidence_kind=EvidenceKind.INFERRED,
                    field=None,
                    span=None,
                    matched_text=None,
                    evidence_text=(
                        f"Not stated in the ad. Usually required for the matched role "
                        f"'{role.role.title}' (importance {importance:g})."
                    ),
                    note=f"inferred from role {role.role.code}",
                )
            )
        return hits


def _skill_order(hit: SkillHit) -> tuple[int, float, str]:
    kinds = {EvidenceKind.OBSERVED: 0, EvidenceKind.INFERRED: 1, EvidenceKind.SYNTHETIC: 2}
    return (kinds[hit.evidence_kind], -hit.confidence, hit.skill.code)


# --------------------------------------------------------------------------- storing
@dataclass
class ProcessResult:
    posting_id: uuid.UUID
    status: str
    analysis: PostingAnalysis | None
    stored: bool
    review_items: int = 0
    error: str | None = None


def has_ground_truth(db: Session, posting_id: uuid.UUID) -> bool:
    generated = ExtractionMethod.GENERATED.value
    return bool(
        db.scalar(
            select(func.count())
            .select_from(PostingSkill)
            .where(PostingSkill.posting_id == posting_id, PostingSkill.method == generated)
        )
        or db.scalar(
            select(func.count())
            .select_from(PostingRole)
            .where(PostingRole.posting_id == posting_id, PostingRole.method == generated)
        )
    )


def process_posting(
    db: Session, intel: JobIntelligence, posting: JobPosting, *, dry_run: bool = False
) -> ProcessResult:
    """Analyse one posting and (unless dry_run) replace its pipeline links. Does not commit."""
    if not dry_run and has_ground_truth(db, posting.id):
        raise GroundTruthConflict(
            "This synthetic posting has generator ground-truth links; processing would replace "
            "them. Use dry_run to see what the pipeline extracts."
        )
    sector = intel.sector_codes.get(posting.sector_id) if posting.sector_id else None
    analysis = intel.analyze(posting.title, posting.description, sector)
    if dry_run:
        return ProcessResult(posting.id, posting.extraction_status, analysis, stored=False)
    bands = intel.config.scoring.job_extraction.proficiency_bands.model_dump()
    review_items = _store(db, posting, analysis, bands)
    posting.extraction_status = ExtractionStatus.DONE.value
    posting.extraction_error = None
    posting.processed_at = datetime.now(UTC)
    db.flush()
    return ProcessResult(
        posting.id, posting.extraction_status, analysis, stored=True, review_items=review_items
    )


def _store(
    db: Session, posting: JobPosting, analysis: PostingAnalysis, bands: dict[str, int]
) -> int:
    pipeline_meta = {"pipeline": PIPELINE_VERSION}
    for model in (PostingSkill, PostingRole):
        db.execute(
            delete(model).where(model.posting_id == posting.id, model.method.not_in(KEPT_METHODS))
        )
    db.execute(
        delete(ReviewItem).where(
            ReviewItem.source_table == "job_posting",
            ReviewItem.source_record_id == str(posting.id),
            ReviewItem.kind.in_(PIPELINE_REVIEW_KINDS),
            ReviewItem.status == ReviewItemStatus.OPEN.value,
        )
    )
    kept_skills = set(
        db.scalars(select(PostingSkill.skill_id).where(PostingSkill.posting_id == posting.id))
    )
    kept_roles = set(
        db.scalars(select(PostingRole.role_id).where(PostingRole.posting_id == posting.id))
    )
    review_items = 0
    for hit in analysis.skills:
        if hit.skill.id in kept_skills:
            continue
        db.add(
            PostingSkill(
                posting_id=posting.id,
                skill_id=hit.skill.id,
                confidence=hit.confidence,
                method=hit.method.value,
                band=bands.get(hit.proficiency.value),
                matched_text=hit.matched_text,
                evidence_kind=hit.evidence_kind.value,
                decision=hit.decision.value,
                proficiency=hit.proficiency.value,
                evidence_text=hit.evidence_text,
                evidence_json={**hit.evidence_json(), **pipeline_meta},
                is_synthetic=posting.is_synthetic,
            )
        )
        if hit.decision == MatchDecision.REVIEW and hit.evidence_kind == EvidenceKind.OBSERVED:
            review_items += _review(
                db,
                posting,
                ReviewKind.SKILL_MAPPING,
                {
                    "phrase": hit.matched_text,
                    "evidence": hit.evidence_text,
                    "method": hit.method.value,
                    "alternatives": list(hit.alternatives),
                },
                hit.confidence,
                suggested_skill_id=hit.skill.id,
            )
    for phrase in analysis.unknown:
        review_items += _review(
            db,
            posting,
            ReviewKind.NEW_SKILL,
            {
                "phrase": phrase.text,
                "evidence": phrase.evidence_text,
                "closest": list(phrase.closest),
            },
            None,
        )
    role = analysis.role
    if role is not None and role.role.id not in kept_roles:
        db.add(
            PostingRole(
                posting_id=posting.id,
                role_id=role.role.id,
                confidence=role.confidence,
                method=role.method.value,
                evidence_kind=role.evidence_kind.value,
                decision=role.decision.value,
                evidence_text=role.evidence_text,
                evidence_json={**role.evidence_json(), **pipeline_meta},
                is_synthetic=posting.is_synthetic,
            )
        )
        if role.decision == MatchDecision.REVIEW:
            review_items += _review(
                db,
                posting,
                ReviewKind.ROLE_MAPPING,
                {
                    "role": role.role.code,
                    "evidence": role.evidence_text,
                    "alternatives": list(role.alternatives),
                },
                role.confidence,
            )
    db.flush()
    return review_items


def _review(
    db: Session,
    posting: JobPosting,
    kind: ReviewKind,
    payload: dict[str, Any],
    confidence: float | None,
    suggested_skill_id: uuid.UUID | None = None,
) -> int:
    db.add(
        ReviewItem(
            kind=kind.value,
            payload_json={
                **payload,
                "posting_title": posting.title,
                "is_synthetic": posting.is_synthetic,
            },
            confidence=confidence,
            suggested_skill_id=suggested_skill_id,
            source_table="job_posting",
            source_record_id=str(posting.id),
        )
    )
    return 1


# --------------------------------------------------------------------------- batches
@dataclass
class BatchReport:
    selected: int = 0
    processed: int = 0
    failed: int = 0
    skills_extracted: int = 0
    roles_matched: int = 0
    review_items: int = 0
    llm_calls: int = 0
    remaining: int = 0
    failures: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def process_batch(
    db: Session,
    intel: JobIntelligence,
    *,
    limit: int = 100,
    retry_failed: bool = False,
    posting_ids: list[uuid.UUID] | None = None,
) -> BatchReport:
    """Process PENDING postings (and FAILED ones with retry_failed), oldest first. Each posting
    runs in its own savepoint and is committed on its own, so one bad posting cannot undo the
    others; it is marked FAILED with the error."""
    statuses = [ExtractionStatus.PENDING.value] + (
        [ExtractionStatus.FAILED.value] if retry_failed else []
    )
    query = select(JobPosting).where(JobPosting.extraction_status.in_(statuses))
    if posting_ids is not None:
        query = query.where(JobPosting.id.in_(posting_ids))
    postings = list(db.scalars(query.order_by(JobPosting.created_at, JobPosting.id).limit(limit)))
    report = BatchReport(selected=len(postings))
    calls_before = intel.llm_calls_made
    for posting in postings:
        try:
            with db.begin_nested():
                result = process_posting(db, intel, posting)
        except Exception as exc:  # one bad posting must not stop the batch
            posting.extraction_status = ExtractionStatus.FAILED.value
            posting.extraction_error = f"{type(exc).__name__}: {exc}"[:1000]
            posting.processed_at = datetime.now(UTC)
            report.failed += 1
            report.failures.append(
                {"posting_id": str(posting.id), "error": posting.extraction_error}
            )
            db.commit()
            continue
        analysis = result.analysis
        assert analysis is not None
        report.processed += 1
        report.skills_extracted += len(analysis.observed)
        report.roles_matched += int(analysis.role is not None)
        report.review_items += result.review_items
        db.commit()
    report.llm_calls = intel.llm_calls_made - calls_before
    remaining = (
        select(func.count())
        .select_from(JobPosting)
        .where(JobPosting.extraction_status.in_(statuses))
    )
    report.remaining = db.scalar(remaining) or 0
    return report


# --------------------------------------------------------------------------- output
def skill_out(hit: SkillHit, posting: JobPosting | None) -> dict[str, Any]:
    return {
        "skill_code": hit.skill.code,
        "skill_name": hit.skill.name,
        "confidence": hit.confidence,
        "method": hit.method.value,
        "decision": hit.decision.value,
        "evidence_kind": hit.evidence_kind.value,
        "evidence_text": hit.evidence_text,
        "matched_text": hit.matched_text,
        "proficiency": hit.proficiency.value,
        "is_synthetic": bool(posting.is_synthetic) if posting is not None else None,
        "evidence": hit.evidence_json(),
        "source_record": source_record(posting) if posting is not None else None,
    }


def role_out(role: RoleHit | None, posting: JobPosting | None) -> dict[str, Any] | None:
    if role is None:
        return None
    return {
        "role_code": role.role.code,
        "role_title": role.role.title,
        "confidence": role.confidence,
        "method": role.method.value,
        "decision": role.decision.value,
        "evidence_kind": role.evidence_kind.value,
        "evidence_text": role.evidence_text,
        "is_synthetic": bool(posting.is_synthetic) if posting is not None else None,
        "evidence": role.evidence_json(),
        "source_record": source_record(posting) if posting is not None else None,
    }


def analysis_out(analysis: PostingAnalysis, posting: JobPosting | None = None) -> dict[str, Any]:
    return {
        "role": role_out(analysis.role, posting),
        "skills": [skill_out(h, posting) for h in analysis.skills],
        "unknown_skill_phrases": [
            {"text": u.text, "evidence_text": u.evidence_text, "closest": list(u.closest)}
            for u in analysis.unknown
        ],
        "llm_calls": analysis.llm_calls,
        "notes": analysis.notes,
    }


def source_record(posting: JobPosting) -> dict[str, Any]:
    """Where a link's evidence comes from: the posting and its provenance."""
    return {
        "table": "job_posting",
        "id": str(posting.id),
        "source": posting.source,
        "source_ref": posting.source_ref,
        "license_note": posting.license_note,
        "ingestion_run_id": str(posting.ingestion_run_id) if posting.ingestion_run_id else None,
        "is_synthetic": posting.is_synthetic,
    }


def posting_out(db: Session, posting: JobPosting) -> dict[str, Any]:
    """A posting with its STORED links and their evidence (what analytics will use)."""
    from app.models import District, JobRole, Skill

    record = source_record(posting)
    skills = []
    rows = db.execute(
        select(PostingSkill, Skill.code, Skill.name)
        .join(Skill, Skill.id == PostingSkill.skill_id)
        .where(PostingSkill.posting_id == posting.id)
        .order_by(
            case(
                (PostingSkill.evidence_kind == EvidenceKind.OBSERVED.value, 0),
                (PostingSkill.evidence_kind == EvidenceKind.SYNTHETIC.value, 1),
                else_=2,
            ),
            PostingSkill.confidence.desc(),
            Skill.code,
        )
    ).all()
    for link, code, name in rows:
        skills.append(
            {
                "skill_code": code,
                "skill_name": name,
                "confidence": link.confidence,
                "method": link.method,
                "decision": link.decision,
                "evidence_kind": link.evidence_kind,
                "evidence_text": link.evidence_text,
                "matched_text": link.matched_text,
                "proficiency": link.proficiency,
                "band": link.band,
                "is_synthetic": link.is_synthetic,
                "evidence": link.evidence_json,
                "source_record": record,
            }
        )
    roles = []
    for link, code, title in db.execute(
        select(PostingRole, JobRole.code, JobRole.title)
        .join(JobRole, JobRole.id == PostingRole.role_id)
        .where(PostingRole.posting_id == posting.id)
    ).all():
        roles.append(
            {
                "role_code": code,
                "role_title": title,
                "confidence": link.confidence,
                "method": link.method,
                "decision": link.decision,
                "evidence_kind": link.evidence_kind,
                "evidence_text": link.evidence_text,
                "is_synthetic": link.is_synthetic,
                "evidence": link.evidence_json,
                "source_record": record,
            }
        )
    district = db.get(District, posting.district_id) if posting.district_id else None
    sector = db.get(Sector, posting.sector_id) if posting.sector_id else None
    return {
        "id": str(posting.id),
        "title": posting.title,
        "description": posting.description,
        "employer": posting.employer_name_raw,
        "district_code": district.code if district else None,
        "sector_code": sector.code if sector else None,
        "location": posting.location_raw,
        "posted_on": posting.posted_on.isoformat(),
        "quarter": posting.quarter,
        "language": posting.language,
        "extraction_status": posting.extraction_status,
        "processed_at": posting.processed_at.isoformat() if posting.processed_at else None,
        "extraction_error": posting.extraction_error,
        "is_synthetic": posting.is_synthetic,
        "provenance": record,
        "roles": roles,
        "skills": skills,
    }
