"""Map a job posting to one canonical job role (job_role table), with evidence.

Signals, in order of strength (all thresholds in config/scoring.yaml `role_matching`):

  title       the title IS a role title or alias (exact / alias), or CONTAINS one
              ("Urgent: EV Technician, Nashik")
  description a role title or alias appears in the description ("EV technician required")
  fuzzy       a spelling variant of a title/alias in the title ("Electrision")
  embedding   the title means the same as a role title/alias (sentence embeddings)
  skills      the skills found in the ad fit the role's skill profile (role_skill)

A text signal is confirmed (bonus) when the role's skills are also in the ad. A role guessed
from skills alone is capped below auto-accept, so a human confirms it. Roles outside the
ad's sector are penalised. If still unsure, an optional LLM may pick ONE of the candidate
roles (capped confidence, always reviewed). Official occupation codes are never used or
invented here.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ProductConfig
from app.llm import ROLE_MATCH_FALLBACK, LLMClient
from app.models import JobRole, RoleSkill, Sector
from app.models.enums import EvidenceKind, ExtractionMethod, MatchDecision
from app.nlp.embeddings import Embedder, EmbeddingUnavailable
from app.nlp.text import normalize_text
from app.nlp.tokens import TextView, analyze_text


@dataclass(frozen=True)
class RoleRef:
    id: uuid.UUID
    code: str
    title: str
    sector: str | None


@dataclass(frozen=True)
class RoleHit:
    role: RoleRef
    confidence: float
    method: ExtractionMethod
    decision: MatchDecision
    evidence_kind: EvidenceKind
    evidence_text: str
    signals: dict[str, Any] = field(default_factory=dict)
    alternatives: tuple[dict[str, Any], ...] = ()
    llm: dict[str, Any] | None = None

    def evidence_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {"signals": self.signals}
        if self.alternatives:
            data["alternatives"] = list(self.alternatives)
        if self.llm:
            data["llm"] = self.llm
        return data


@dataclass
class _Candidate:
    role: RoleRef
    text_score: float = 0.0
    text_method: ExtractionMethod | None = None
    text_evidence: str | None = None
    skill_score: float = 0.0
    skill_overlap: list[str] = field(default_factory=list)
    score: float = 0.0


class RoleMatcher:
    def __init__(
        self,
        db: Session,
        config: ProductConfig,
        *,
        embedder: Embedder | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.settings = config.scoring.role_matching
        self.llm_cap = config.scoring.skill_matching.llm_fallback_max_confidence
        self.floor = config.llm.embeddings.similarity_floor
        self.embedder = embedder
        self.llm = llm
        self.llm_calls: list[dict[str, Any]] = []
        self._load(db)
        self._vectors: list[list[float]] | None = None

    def _load(self, db: Session) -> None:
        rows = db.execute(
            select(JobRole.id, JobRole.code, JobRole.title, JobRole.aliases, Sector.code).join(
                Sector, Sector.id == JobRole.sector_id
            )
        ).all()
        self.roles = {r.id: RoleRef(r.id, r.code, r.title, r[4]) for r in rows}
        # word sequence -> [(role, "exact" | "alias", original text)]
        self.terms: dict[tuple[str, ...], list[tuple[RoleRef, str, str]]] = {}
        for role_id, _, title, aliases, _ in rows:
            role = self.roles[role_id]
            for text, kind in [(title, "exact"), *((a, "alias") for a in aliases or [])]:
                if words := tuple(normalize_text(text).split()):
                    owners = self.terms.setdefault(words, [])
                    if all(o[0] != role for o in owners):
                        owners.append((role, kind, text))
        self.term_list = list(self.terms)
        self.term_texts = [" ".join(t) for t in self.term_list]
        self.profiles: dict[uuid.UUID, dict[uuid.UUID, float]] = {}
        for role_id, skill_id, importance in db.execute(
            select(RoleSkill.role_id, RoleSkill.skill_id, RoleSkill.importance)
        ):
            self.profiles.setdefault(role_id, {})[skill_id] = importance

    # ------------------------------------------------------------------ signals
    def _text_signals(
        self, candidates: dict[uuid.UUID, _Candidate], title: TextView, description: TextView
    ) -> None:
        s = self.settings.title_confidence
        whole_title = tuple(title.norms)

        def offer(role: RoleRef, score: float, method: ExtractionMethod, evidence: str) -> None:
            c = candidates.setdefault(role.id, _Candidate(role))
            if score > c.text_score:
                c.text_score, c.text_method, c.text_evidence = score, method, evidence

        for owners in [self.terms.get(whole_title, [])]:
            for role, kind, text in owners:
                score = s.exact if kind == "exact" else s.alias
                method = ExtractionMethod.EXACT if kind == "exact" else ExtractionMethod.ALIAS
                offer(role, score, method, f"title '{title.text}' = role {kind} '{text}'")
        # Titles/descriptions that CONTAIN a role term; longer terms first.
        for words in sorted(self.terms, key=len, reverse=True):
            for view, score, where in (
                (title, s.contained, "title"),
                (description, s.description, "description"),
            ):
                starts = view.find(words)
                if not starts:
                    continue
                start = starts[0]
                sent_first, sent_end = view.sentence_of(start)
                quote = view.quote(sent_first, sent_end)[:300]
                for role, kind, _ in self.terms[words]:
                    method = ExtractionMethod.EXACT if kind == "exact" else ExtractionMethod.ALIAS
                    offer(
                        role,
                        score,
                        method,
                        f"{where} mentions '{view.quote(start, start + len(words))}': {quote}",
                    )
        # Spelling variants of a role term inside the title.
        if self.term_texts:
            norms = title.norms
            for size in range(1, min(len(norms), max(map(len, self.term_list))) + 1):
                for i in range(len(norms) - size + 1):
                    text = " ".join(norms[i : i + size])
                    if len(text) < 5:
                        continue
                    match = process.extractOne(
                        text,
                        self.term_texts,
                        scorer=fuzz.ratio,
                        score_cutoff=self.settings.fuzzy_min_score * 100,
                    )
                    if match and match[1] < 100:
                        for role, _, term in self.terms[self.term_list[match[2]]]:
                            offer(
                                role,
                                match[1] / 100.0,
                                ExtractionMethod.FUZZY,
                                f"title '{title.quote(i, i + size)}' looks like role term '{term}'",
                            )

    def _meaning(self, candidates: dict[uuid.UUID, _Candidate], title: TextView) -> str | None:
        if self.embedder is None or not title.tokens or not self.term_list:
            return None
        try:
            if self._vectors is None:
                self._vectors = self.embedder.embed_documents(self.term_texts)
            query = self.embedder.embed_queries([title.text])[0]
        except EmbeddingUnavailable as exc:
            return f"embeddings unavailable: {exc}"
        for words, vector in zip(self.term_list, self._vectors, strict=True):
            similarity = sum(a * b for a, b in zip(query, vector, strict=True)) / (
                math.sqrt(sum(a * a for a in query)) * math.sqrt(sum(b * b for b in vector)) or 1.0
            )
            score = max(0.0, min(1.0, (similarity - self.floor) / (1.0 - self.floor)))
            if score <= 0:
                continue
            for role, _, term in self.terms[words]:
                c = candidates.setdefault(role.id, _Candidate(role))
                if score > c.text_score:
                    c.text_score = score
                    c.text_method = ExtractionMethod.EMBEDDING
                    c.text_evidence = (
                        f"title '{title.text}' means about the same as '{term}' "
                        f"(similarity {similarity:.3f})"
                    )
        return None

    def _skill_signals(
        self, candidates: dict[uuid.UUID, _Candidate], skills: Mapping[uuid.UUID, tuple[str, float]]
    ) -> None:
        """How typical the ad's skills are for each role: the average, over the skills
        found in the ad, of (importance for the role x match confidence). Ads rarely list a
        role's whole profile, so this does not punish short ads."""
        if not skills:
            return
        for role_id, profile in self.profiles.items():
            overlap = [
                (skill_id, importance)
                for skill_id, importance in profile.items()
                if skill_id in skills
            ]
            if not overlap:
                continue
            score = sum(importance * skills[skill_id][1] for skill_id, importance in overlap) / len(
                skills
            )
            c = candidates.setdefault(role_id, _Candidate(self.roles[role_id]))
            c.skill_score = score
            c.skill_overlap = sorted(skills[skill_id][0] for skill_id, _ in overlap)

    # ------------------------------------------------------------------ main entry point
    def match(
        self,
        title: str,
        description: str | None,
        skills: Mapping[uuid.UUID, tuple[str, float]],
        sector: str | None = None,
    ) -> RoleHit | None:
        """skills: skill id -> (code, confidence) of the OBSERVED skills found in the ad."""
        s = self.settings
        title_view, description_view = analyze_text(title), analyze_text(description)
        candidates: dict[uuid.UUID, _Candidate] = {}
        self._text_signals(candidates, title_view, description_view)
        note = self._meaning(candidates, title_view)
        self._skill_signals(candidates, skills)
        for c in candidates.values():
            if c.text_method == ExtractionMethod.EMBEDDING and c.skill_score == 0:
                # Similar-sounding titles are not enough ("Accountant" ~ "Electrician"):
                # a meaning-only title match needs at least one of the role's skills.
                c.text_score, c.text_method, c.text_evidence = 0.0, None, None
            if c.text_score > 0:
                c.score = min(1.0, c.text_score + s.skill_agreement_bonus * c.skill_score)
            else:
                c.score = c.skill_score * s.skills_only_factor
            if sector and c.role.sector and c.role.sector != sector:
                c.score *= s.sector_mismatch_factor
        ranked = sorted(candidates.values(), key=lambda c: (-c.score, c.role.code))
        ranked = [c for c in ranked if c.score > 0]
        if not ranked:
            return None
        best = ranked[0]
        ambiguous = len(ranked) > 1 and best.score - ranked[1].score < s.ambiguity_margin
        confidence = best.score
        if confidence >= s.auto_accept_confidence and not ambiguous:
            decision: MatchDecision | None = MatchDecision.ACCEPT
        elif confidence >= s.min_confidence:
            decision = MatchDecision.REVIEW
        else:
            decision = None
        method = best.text_method or ExtractionMethod.SKILL_PROFILE
        evidence = (
            best.text_evidence or f"skills in the ad fit this role: {', '.join(best.skill_overlap)}"
        )
        alternatives = tuple({"role": c.role.code, "score": round(c.score, 3)} for c in ranked[1:4])
        signals = {
            "text_score": round(best.text_score, 4),
            "text_method": best.text_method.value if best.text_method else None,
            "skill_score": round(best.skill_score, 4),
            "skills_in_common": best.skill_overlap,
            "ambiguous": ambiguous,
            **({"sector_hint": sector} if sector else {}),
            **({"note": note} if note else {}),
        }
        hit = None
        if decision is not None:
            hit = RoleHit(
                best.role,
                round(confidence, 4),
                method,
                decision,
                EvidenceKind.OBSERVED,
                evidence,
                signals,
                alternatives,
            )
        if (hit is None or hit.decision != MatchDecision.ACCEPT) and self.llm is not None:
            picked = self._llm_pick(title_view.text, description_view.text, ranked[:5])
            if picked is not None:
                role, provenance = picked
                return RoleHit(
                    role,
                    self.llm_cap,
                    ExtractionMethod.LLM,
                    MatchDecision.REVIEW,
                    EvidenceKind.OBSERVED,
                    f"an LLM chose this role among {len(ranked[:5])} candidates for the ad "
                    f"'{title_view.text}'",
                    signals,
                    tuple(
                        {"role": c.role.code, "score": round(c.score, 3)}
                        for c in ranked[:4]
                        if c.role != role
                    ),
                    provenance,
                )
        return hit

    def _llm_pick(
        self, title: str, description: str, ranked: list[_Candidate]
    ) -> tuple[RoleRef, dict[str, Any]] | None:
        if self.llm is None or not ranked:
            return None
        payload = {
            "title": title,
            "text": description[:1500],
            "candidates": [{"code": c.role.code, "title": c.role.title} for c in ranked],
        }
        answer = self.llm.run(ROLE_MATCH_FALLBACK, payload)
        provenance = answer.provenance()
        self.llm_calls.append(provenance)
        if not answer.ok or answer.output is None or answer.output.role_code is None:
            return None
        return next(
            ((c.role, provenance) for c in ranked if c.role.code == answer.output.role_code), None
        )
