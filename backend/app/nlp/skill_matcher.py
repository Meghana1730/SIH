"""Match a free-text phrase to a skill in the vocabulary.

Steps, cheapest and most certain first (docs/04-architecture.md §4.1); the first confident
step wins:

  1. exact     the normalised text equals a skill name               confidence 1.0
  2. alias     the normalised text equals a curated alias            alias_confidence
  3. fuzzy     a spelling variant of a name/alias (rapidfuzz)       spelling similarity
  4. embedding the closest meaning (sentence embeddings + pgvector)  calibrated similarity
  5. llm       OPTIONAL last resort: an LLM may only pick one of the candidates found above;
               its answer is capped below auto-accept, so a human always checks it.

Every result carries a confidence (0-1), the method, and a decision:
  accept   (confidence >= auto_accept_confidence)
  review   (>= min_confidence: goes to the human review queue)
  no_match (below: nothing is assigned)
Similarity is NOT certainty: close meanings can still be wrong, which is why the review band
exists. All thresholds come from config (scoring.yaml skill_matching, llm.yaml embeddings).
"""

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ProductConfig
from app.models import Skill, SkillAlias
from app.nlp.embeddings import Embedder, EmbeddingUnavailable
from app.nlp.skill_embeddings import nearest_skills
from app.nlp.text import normalize_text

Method = Literal["exact", "alias", "fuzzy", "embedding", "llm", "none"]
Decision = Literal["accept", "review", "no_match"]


@dataclass(frozen=True)
class SkillRef:
    id: uuid.UUID
    code: str
    name: str


@dataclass(frozen=True)
class Candidate:
    skill: SkillRef
    score: float  # confidence-scale score (0-1) of this candidate
    method: Method
    matched_text: str
    similarity: float | None = None  # raw cosine similarity, for embedding candidates


@dataclass(frozen=True)
class MatchResult:
    input: str
    normalized: str
    matched_skill: SkillRef | None
    matched_text: str | None
    confidence: float
    method: Method
    decision: Decision
    alternatives: tuple[Candidate, ...] = field(default=())
    note: str | None = None
    similarity: float | None = None  # raw cosine similarity when method == "embedding"

    def to_dict(self) -> dict[str, Any]:
        return {
            "input": self.input,
            "matched_skill": self.matched_skill.name if self.matched_skill else None,
            "matched_skill_code": self.matched_skill.code if self.matched_skill else None,
            "matched_text": self.matched_text,
            "confidence": round(self.confidence, 3),
            "method": self.method,
            "decision": self.decision,
            **({"similarity": round(self.similarity, 3)} if self.similarity is not None else {}),
            "alternatives": [
                {
                    "skill": c.skill.name,
                    "score": round(c.score, 3),
                    "method": c.method,
                    **({"similarity": round(c.similarity, 3)} if c.similarity is not None else {}),
                }
                for c in self.alternatives
            ],
            **({"note": self.note} if self.note else {}),
        }


# An LLM fallback receives the phrase and the candidates and returns the code of ONE of them
# (or None). It can never introduce a skill that is not already a candidate.
LlmFallback = Callable[[str, Sequence[Candidate]], str | None]


class SkillMatcher:
    """Loads the vocabulary once; call match() for each phrase."""

    def __init__(
        self,
        db: Session,
        config: ProductConfig,
        embedder: Embedder | None = None,
        llm_fallback: LlmFallback | None = None,
    ) -> None:
        self._db = db
        self._settings = config.scoring.skill_matching
        self._floor = config.llm.embeddings.similarity_floor
        self._embedder = embedder
        llm = config.llm.llm
        self._llm_fallback = (
            llm_fallback
            if llm_fallback is not None
            and llm.mode != "off"
            and llm.tasks.skill_match_fallback.enabled
            else None
        )
        self._load_vocabulary()

    # ------------------------------------------------------------ vocabulary
    def _load_vocabulary(self) -> None:
        self._by_name: dict[str, SkillRef] = {}
        self._by_alias: dict[str, set[SkillRef]] = {}
        refs: dict[uuid.UUID, SkillRef] = {}
        for skill_id, code, name in self._db.execute(select(Skill.id, Skill.code, Skill.name)):
            ref = SkillRef(skill_id, code, name)
            refs[skill_id] = ref
            self._by_name[normalize_text(name)] = ref
        for skill_id, alias in self._db.execute(select(SkillAlias.skill_id, SkillAlias.alias)):
            self._by_alias.setdefault(normalize_text(alias), set()).add(refs[skill_id])
        # Fuzzy-matching choices: every normalised name and alias, with its owner.
        self._fuzzy_texts: list[str] = [*self._by_name]
        self._fuzzy_owners: list[SkillRef] = [*self._by_name.values()]
        for text, owners in self._by_alias.items():
            for owner in owners:
                self._fuzzy_texts.append(text)
                self._fuzzy_owners.append(owner)

    # ------------------------------------------------------------ helpers
    def _decide(self, confidence: float) -> Decision:
        if confidence >= self._settings.auto_accept_confidence:
            return "accept"
        if confidence >= self._settings.min_confidence:
            return "review"
        return "no_match"

    def _calibrate(self, similarity: float) -> float:
        """Cosine similarity -> confidence: the floor maps to 0, a perfect 1.0 stays 1."""
        return max(0.0, min(1.0, (similarity - self._floor) / (1.0 - self._floor)))

    def _result(
        self,
        text: str,
        normalized: str,
        best: Candidate | None,
        alternatives: Sequence[Candidate] = (),
        note: str | None = None,
    ) -> MatchResult:
        if best is None:
            return MatchResult(
                text, normalized, None, None, 0.0, "none", "no_match", tuple(alternatives), note
            )
        decision = self._decide(best.score)
        others = tuple(c for c in alternatives if c.skill != best.skill)
        if decision == "no_match":
            # Nothing is assigned, but the closest candidates are kept for information.
            return MatchResult(
                text, normalized, None, None, best.score, "none", decision, (best, *others), note
            )
        return MatchResult(
            input=text,
            normalized=normalized,
            matched_skill=best.skill,
            matched_text=best.matched_text,
            confidence=best.score,
            method=best.method,
            decision=decision,
            alternatives=others,
            note=note,
            similarity=best.similarity,
        )

    def _fuzzy(self, normalized: str) -> list[Candidate]:
        if len(normalized) < self._settings.fuzzy.min_input_length or not self._fuzzy_texts:
            return []
        found = process.extract(
            normalized,
            self._fuzzy_texts,
            scorer=fuzz.token_sort_ratio,  # ignores word order; not fooled by substrings
            limit=self._settings.embedding.top_k * 2,
        )
        best: dict[SkillRef, Candidate] = {}
        for text, score, index in found:
            owner = self._fuzzy_owners[index]
            candidate = Candidate(owner, score / 100.0, "fuzzy", text)
            if owner not in best or candidate.score > best[owner].score:
                best[owner] = candidate
        return sorted(best.values(), key=lambda c: c.score, reverse=True)

    def _semantic(
        self, text: str, vector: list[float] | None = None
    ) -> tuple[list[Candidate], str | None]:
        if self._embedder is None:
            return [], "embeddings are switched off"
        try:
            if vector is None:
                vector = self._embedder.embed_queries([text])[0]
        except EmbeddingUnavailable as exc:
            return [], f"embeddings unavailable: {exc}"
        hits = nearest_skills(
            self._db, vector, self._embedder.space, self._settings.embedding.top_k
        )
        candidates = [
            Candidate(
                SkillRef(h.skill_id, h.code, h.name),
                self._calibrate(h.similarity),
                "embedding",
                h.matched_text,
                h.similarity,
            )
            for h in hits
        ]
        return candidates, None

    # ------------------------------------------------------------ main entry point
    def match(self, text: str, _vector: list[float] | None = None) -> MatchResult:
        normalized = normalize_text(text)
        if not normalized:
            return self._result(text, normalized, None, note="empty input")

        # 1. exact canonical name
        if (skill := self._by_name.get(normalized)) is not None:
            return self._result(text, normalized, Candidate(skill, 1.0, "exact", skill.name))

        # 2. curated alias
        if (owners := self._by_alias.get(normalized)) is not None:
            if len(owners) == 1:
                (skill,) = owners
                return self._result(
                    text,
                    normalized,
                    Candidate(skill, self._settings.alias_confidence, "alias", normalized),
                )
            # The same alias belongs to several skills: a human must decide.
            review_score = self._settings.min_confidence
            candidates = [
                Candidate(skill, review_score, "alias", normalized)
                for skill in sorted(owners, key=lambda s: s.name)
            ]
            return self._result(
                text, normalized, candidates[0], candidates, note="alias matches several skills"
            )

        # 3. fuzzy (spelling variants)
        fuzzy = self._fuzzy(normalized)
        if fuzzy and fuzzy[0].score >= self._settings.fuzzy.min_score:
            return self._result(text, normalized, fuzzy[0], fuzzy)

        # 4. embedding similarity (meaning). Fuzzy scores below fuzzy.min_score mean "not a
        # spelling variant" ("Accounting" vs "grounding"), so they never decide a match; they
        # are only listed as alternatives for a human reviewer.
        semantic, note = self._semantic(text, _vector)
        best = semantic[0] if semantic else None
        alternatives = sorted([*semantic, *fuzzy], key=lambda c: c.score, reverse=True)
        result = self._result(text, normalized, best, alternatives, note)

        # 5. optional LLM fallback: only when still unsure, and only among the candidates
        candidates = alternatives
        if self._llm_fallback is not None and result.decision != "accept" and candidates:
            chosen = self._llm_fallback(text, candidates)
            by_code = {c.skill.code: c for c in candidates}
            if chosen in by_code:
                pick = by_code[chosen]
                capped = self._settings.llm_fallback_max_confidence  # always below auto-accept
                llm_candidate = Candidate(pick.skill, capped, "llm", pick.matched_text)
                return self._result(text, normalized, llm_candidate, candidates, note)
        return result

    def match_many(self, texts: Sequence[str]) -> list[MatchResult]:
        """Match several phrases. Phrases that need the embedding step are embedded in ONE
        batch, which is several times faster than one at a time."""
        needs_meaning = [
            text
            for text in texts
            if (norm := normalize_text(text))
            and norm not in self._by_name
            and norm not in self._by_alias
        ]
        vectors: dict[str, list[float]] = {}
        if self._embedder is not None and needs_meaning:
            try:
                unique = list(dict.fromkeys(needs_meaning))
                vectors = dict(zip(unique, self._embedder.embed_queries(unique), strict=True))
            except EmbeddingUnavailable:
                vectors = {}  # match() reports the reason per phrase
        return [self.match(text, vectors.get(text)) for text in texts]
