"""Find the skills a job posting asks for, with evidence (docs/06-job-intelligence.md).

    extractor = SkillExtractor(db, config, embedder=..., llm=...)   # loads the vocabulary once
    found = extractor.extract(title, description)

Steps, cheapest and most certain first; each step only looks at words that no earlier step
has explained:

  1. exact     a skill name appears in the text                      confidence 1.0
  2. alias     a curated alias appears (English, Hindi or Marathi)   alias_confidence
  3. fuzzy     a run of words is a spelling variant of a name/alias  spelling similarity
  4. embedding leftover phrases (split at "and", "with", ...; filler words removed) are
               matched by meaning with the SkillMatcher (sentence embeddings + pgvector)
  5. llm       OPTIONAL: only for phrases that are still uncertain AND have a plausible
               candidate; the LLM may only pick one of those candidates (capped confidence,
               always reviewed). Optionally (off by default) an LLM may QUOTE skill phrases
               from ads where nothing was found; they are then matched like any phrase.

Every hit is OBSERVED: it quotes the words of the ad that matched and the clause around
them. Leftover phrases in a "skills" sentence that match nothing become NEW-skill
candidates for the review queue (skills are never added automatically).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ProductConfig
from app.llm import SKILL_MATCH_FALLBACK, SKILL_PHRASE_EXTRACTION, LLMClient
from app.models import JobRole, Skill, SkillAlias
from app.models.enums import EvidenceKind, ExtractionMethod, MatchDecision, Proficiency
from app.nlp.cues import Cue, Cues, load_cues
from app.nlp.embeddings import Embedder
from app.nlp.skill_matcher import Candidate, MatchResult, SkillMatcher, SkillRef
from app.nlp.text import normalize_text
from app.nlp.tokens import TextView, analyze_text

METHODS = {
    "exact": ExtractionMethod.EXACT,
    "alias": ExtractionMethod.ALIAS,
    "fuzzy": ExtractionMethod.FUZZY,
    "embedding": ExtractionMethod.EMBEDDING,
    "llm": ExtractionMethod.LLM,
}
FIELDS = ("title", "description")


@dataclass(frozen=True)
class SkillHit:
    skill: SkillRef
    confidence: float
    method: ExtractionMethod
    decision: MatchDecision
    evidence_kind: EvidenceKind
    field: str | None  # "title" | "description" (None for INFERRED)
    span: tuple[int, int] | None  # character offsets in that field's text
    matched_text: str | None  # the words of the ad that matched
    evidence_text: str  # the clause containing them (or why it was inferred)
    vocabulary_term: str | None = None  # the skill name / alias that was matched
    proficiency: Proficiency = Proficiency.UNKNOWN
    proficiency_cue: Cue | None = None
    similarity: float | None = None
    alternatives: tuple[dict[str, Any], ...] = ()
    mentions: int = 1
    phrase_source: str = "text"  # "text" or "llm" (an LLM quoted the phrase)
    llm: dict[str, Any] | None = None  # provenance of the LLM answer, if one was used
    note: str | None = None

    def evidence_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "field": self.field,
            "span": list(self.span) if self.span else None,
            "matched_text": self.matched_text,
            "vocabulary_term": self.vocabulary_term,
            "mentions": self.mentions,
            "phrase_source": self.phrase_source,
            "proficiency_note": "requested in the ad, not a certified level",
        }
        if self.proficiency_cue:
            data["proficiency_cue"] = {
                "text": self.proficiency_cue.text,
                "source": self.proficiency_cue.source,
            }
        if self.similarity is not None:
            data["similarity"] = round(self.similarity, 4)
        if self.alternatives:
            data["alternatives"] = list(self.alternatives)
        if self.llm:
            data["llm"] = self.llm
        if self.note:
            data["note"] = self.note
        return data


@dataclass(frozen=True)
class UnknownPhrase:
    """Words in a "skills" sentence that match no known skill (a NEW-skill candidate)."""

    field: str
    text: str
    span: tuple[int, int]
    evidence_text: str
    closest: tuple[dict[str, Any], ...] = ()


@dataclass
class SkillExtraction:
    hits: list[SkillHit] = field(default_factory=list)
    unknown: list[UnknownPhrase] = field(default_factory=list)
    llm_calls: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    views: dict[str, TextView] = field(default_factory=dict)


@dataclass(frozen=True)
class _Phrase:
    field: str
    first: int  # token range in that field
    end: int
    text: str


def _alternatives(candidates: Sequence[Candidate], keep: uuid.UUID | None) -> tuple[dict, ...]:
    return tuple(
        {"skill": c.skill.code, "score": round(c.score, 3), "method": c.method}
        for c in candidates[:3]
        if c.skill.id != keep
    )


class SkillExtractor:
    def __init__(
        self,
        db: Session,
        config: ProductConfig,
        *,
        embedder: Embedder | None = None,
        llm: LLMClient | None = None,
        cues: Cues | None = None,
    ) -> None:
        self.config = config
        self.settings = config.scoring.job_extraction
        self.matching = config.scoring.skill_matching
        self.cues = cues or load_cues()
        self.llm = llm
        self._llm_log: list[dict[str, Any]] = []
        self._llm_by_phrase: dict[str, dict[str, Any]] = {}
        self._contexts: dict[str, str] = {}
        self.matcher = SkillMatcher(
            db, config, embedder, llm_fallback=self._llm_pick if llm is not None else None
        )
        self._load_terms(db)

    # ------------------------------------------------------------------ vocabulary
    def _load_terms(self, db: Session) -> None:
        """Every skill name and alias as a word sequence -> the skills it names."""
        refs: dict[uuid.UUID, SkillRef] = {}
        self.terms: dict[tuple[str, ...], list[tuple[SkillRef, str, str]]] = {}
        for skill_id, code, name in db.execute(select(Skill.id, Skill.code, Skill.name)):
            ref = refs[skill_id] = SkillRef(skill_id, code, name)
            if words := tuple(normalize_text(name).split()):
                self.terms.setdefault(words, []).append((ref, "exact", name))
        for skill_id, alias in db.execute(select(SkillAlias.skill_id, SkillAlias.alias)):
            if words := tuple(normalize_text(alias).split()):
                entry = (refs[skill_id], "alias", alias)
                owners = self.terms.setdefault(words, [])
                if all(o[0] != entry[0] for o in owners):
                    owners.append(entry)
        self.longest_term = max((len(t) for t in self.terms), default=0)
        self.term_texts = [" ".join(t) for t in self.terms]
        self.term_keys = list(self.terms)
        # Job-role titles/aliases ("EV technician") are role evidence, not skill phrases.
        self.role_terms: set[tuple[str, ...]] = set()
        for title, aliases in db.execute(select(JobRole.title, JobRole.aliases)):
            for text in [title, *(aliases or [])]:
                if words := tuple(normalize_text(text).split()):
                    self.role_terms.add(words)

    # ------------------------------------------------------------------ public
    def extract(self, title: str, description: str | None) -> SkillExtraction:
        self._llm_log = []
        self._llm_by_phrase = {}
        self._contexts = {}
        result = SkillExtraction(
            views={"title": analyze_text(title), "description": analyze_text(description)}
        )
        covered: dict[str, set[int]] = {name: set() for name in FIELDS}
        hits: list[SkillHit] = []
        for name in FIELDS:
            view = result.views[name]
            hits += self._dictionary(name, view, covered[name])
            hits += self._fuzzy(name, view, covered[name])
        hits += self._by_meaning(result, covered)
        if not hits:
            hits += self._llm_phrases(result, covered)
        result.hits = self._merge([self._with_proficiency(h, result.views) for h in hits])
        result.llm_calls = list(self._llm_log)
        return result

    # ------------------------------------------------------------------ 1-2 names and aliases
    def _hit(
        self,
        name: str,
        view: TextView,
        first: int,
        end: int,
        skill: SkillRef,
        confidence: float,
        method: str,
        term: str | None,
        **extra: Any,
    ) -> SkillHit:
        decision = (
            MatchDecision.ACCEPT
            if confidence >= self.matching.auto_accept_confidence
            else MatchDecision.REVIEW
        )
        seg_first, seg_end = view.segment_of(first)
        sent_first, sent_end = view.sentence_of(first)
        clause = view.quote(min(seg_first, sent_first), max(seg_end, sent_end))
        return SkillHit(
            skill=skill,
            confidence=round(confidence, 4),
            method=METHODS[method],
            decision=decision,
            evidence_kind=EvidenceKind.OBSERVED,
            field=name,
            span=(view.tokens[first].start, view.tokens[end - 1].end),
            matched_text=view.quote(first, end),
            evidence_text=clause[:400],
            vocabulary_term=term,
            **extra,
        )

    def _dictionary(self, name: str, view: TextView, covered: set[int]) -> list[SkillHit]:
        hits = []
        norms = view.norms
        for seg_first, seg_end in view.segments:
            i = seg_first
            while i < seg_end:
                for size in range(min(self.longest_term, seg_end - i), 0, -1):
                    owners = self.terms.get(tuple(norms[i : i + size]))
                    if not owners:
                        continue
                    if len(owners) == 1:
                        skill, method, term = owners[0]
                        confidence = 1.0 if method == "exact" else self.matching.alias_confidence
                        hits.append(
                            self._hit(name, view, i, i + size, skill, confidence, method, term)
                        )
                    else:  # the same words name several skills: a human decides
                        first_owner, *others = sorted(owners, key=lambda o: o[0].code)
                        hits.append(
                            self._hit(
                                name,
                                view,
                                i,
                                i + size,
                                first_owner[0],
                                self.matching.min_confidence,
                                first_owner[1],
                                first_owner[2],
                                alternatives=tuple(
                                    {"skill": o[0].code, "method": o[1]} for o in others
                                ),
                                note="these words name several skills",
                            )
                        )
                    covered.update(range(i, i + size))
                    i += size
                    break
                else:
                    i += 1
        return hits

    # ------------------------------------------------------------------ 3 spelling variants
    def _fuzzy(self, name: str, view: TextView, covered: set[int]) -> list[SkillHit]:
        if not self.term_texts:
            return []
        settings, fuzzy = self.settings, self.matching.fuzzy
        norms = view.norms
        found: list[tuple[float, int, int, int]] = []  # (score, first, end, term index)
        for seg_first, seg_end in view.segments:
            for run_first, run_end in _runs(seg_first, seg_end, covered):
                longest = min(self.longest_term + settings.fuzzy_extra_words, run_end - run_first)
                for size in range(1, longest + 1):
                    for i in range(run_first, run_end - size + 1):
                        text = " ".join(norms[i : i + size])
                        if len(text) < fuzzy.min_input_length:
                            continue
                        if size == 1 and len(text) < settings.fuzzy_min_single_word_chars:
                            continue
                        match = process.extractOne(
                            text,
                            self.term_texts,
                            scorer=fuzz.ratio,
                            score_cutoff=fuzzy.min_score * 100,
                        )
                        if match is None:
                            continue
                        _, score, index = match
                        if abs(len(self.term_keys[index]) - size) <= settings.fuzzy_extra_words:
                            found.append((score / 100.0, i, i + size, index))
        hits = []
        taken: set[int] = set()
        for score, first, end, index in sorted(found, key=lambda f: (-f[0], -(f[2] - f[1]), f[1])):
            if taken & set(range(first, end)):
                continue
            owners = self.terms[self.term_keys[index]]
            skill, _, term = sorted(owners, key=lambda o: o[0].code)[0]
            confidence = score if len(owners) == 1 else self.matching.min_confidence
            hits.append(self._hit(name, view, first, end, skill, confidence, "fuzzy", term))
            taken.update(range(first, end))
        covered.update(taken)
        return hits

    # ------------------------------------------------------------------ 4-5 meaning (+ LLM)
    def _phrases(self, name: str, view: TextView, covered: set[int]) -> list[_Phrase]:
        """Leftover words split into short phrases at connectors, filler words removed."""
        phrases = []
        norms = view.norms
        for seg_first, seg_end in view.segments:
            current: list[int] = []
            for i in [*range(seg_first, seg_end), None]:
                stop = i is None or i in covered or norms[i] in self.cues.connectors
                if not stop:
                    current.append(i)  # type: ignore[arg-type]
                    continue
                words = current
                while words and (norms[words[0]] in self.cues.filler or norms[words[0]].isdigit()):
                    words = words[1:]
                while words and (
                    norms[words[-1]] in self.cues.filler or norms[words[-1]].isdigit()
                ):
                    words = words[:-1]
                useful = [w for w in words if len(norms[w]) >= 3 and not norms[w].isdigit()]
                if words and useful and len(words) <= self.settings.max_phrase_words:
                    phrases.append(
                        _Phrase(name, words[0], words[-1] + 1, view.quote(words[0], words[-1] + 1))
                    )
                current = []
        return phrases

    def _by_meaning(self, result: SkillExtraction, covered: dict[str, set[int]]) -> list[SkillHit]:
        view = result.views["description"]
        # Words naming a job role are left to role matching.
        role_words = set(covered["description"])
        for words in self.role_terms:
            for start in view.find(words):
                role_words.update(range(start, start + len(words)))
        phrases = self._phrases("description", view, role_words)
        budget = self.settings.max_phrases_per_posting
        if len(phrases) > budget:
            result.notes.append(
                f"{len(phrases) - budget} phrases skipped (max_phrases_per_posting)"
            )
            phrases = phrases[:budget]
        for phrase in phrases:
            first, end = view.segment_of(phrase.first)
            self._contexts[phrase.text] = view.quote(first, end)
        matches = self.matcher.match_many([p.text for p in phrases]) if phrases else []
        hits = []
        for phrase, match in zip(phrases, matches, strict=True):
            if match.matched_skill is not None and match.decision != "no_match":
                hits.append(self._from_match(phrase, view, match, "text"))
                covered["description"].update(range(phrase.first, phrase.end))
            elif self.cues.has_skill_context(view, phrase.first, phrase.end):
                result.unknown.append(
                    UnknownPhrase(
                        "description",
                        phrase.text,
                        (view.tokens[phrase.first].start, view.tokens[phrase.end - 1].end),
                        view.quote(*view.segment_of(phrase.first)),
                        _alternatives(match.alternatives, None),
                    )
                )
            if match.note and match.note not in result.notes:
                result.notes.append(match.note)
        return hits

    def _from_match(
        self, phrase: _Phrase, view: TextView, match: MatchResult, source: str
    ) -> SkillHit:
        assert match.matched_skill is not None
        method = match.method if match.method in METHODS else "embedding"
        return self._hit(
            phrase.field,
            view,
            phrase.first,
            phrase.end,
            match.matched_skill,
            match.confidence,
            method,
            match.matched_text,
            similarity=match.similarity,
            alternatives=_alternatives(match.alternatives, match.matched_skill.id),
            phrase_source=source,
            llm=self._llm_by_phrase.get(phrase.text) if method == "llm" else None,
        )

    def _llm_pick(self, text: str, candidates: Sequence[Candidate]) -> str | None:
        """SkillMatcher's LLM fallback: only when a candidate is plausible, only among them."""
        if self.llm is None or not candidates:
            return None
        if max(c.score for c in candidates) < self.settings.llm_min_candidate_score:
            return None
        payload = {
            "phrase": text,
            "context": self._contexts.get(text, text),
            "candidates": [{"code": c.skill.code, "name": c.skill.name} for c in candidates[:5]],
        }
        answer = self.llm.run(SKILL_MATCH_FALLBACK, payload)
        provenance = answer.provenance()
        self._llm_log.append(provenance)
        self._llm_by_phrase[text] = provenance
        return answer.output.skill_code if answer.ok and answer.output else None

    def _llm_phrases(self, result: SkillExtraction, covered: dict[str, set[int]]) -> list[SkillHit]:
        """Optional (task skill_phrase_extraction): let an LLM QUOTE skill phrases from an ad in
        which nothing was found. The quotes are matched like any other phrase."""
        view = result.views["description"]
        if self.llm is None or len(view.tokens) < self.settings.llm_phrase_extraction_min_words:
            return []
        if not getattr(self.config.llm.llm.tasks, SKILL_PHRASE_EXTRACTION.name).enabled:
            return []
        answer = self.llm.run(SKILL_PHRASE_EXTRACTION, {"text": view.text})
        provenance = answer.provenance()
        self._llm_log.append(provenance)
        if not answer.ok or answer.output is None:
            result.notes.append(f"LLM phrase extraction failed: {answer.error}")
            return []
        phrases = []
        for quoted in answer.output.phrases:
            words = tuple(normalize_text(quoted).split())
            starts = view.find(words) if words else []
            if starts:
                start = starts[0]
                phrases.append(
                    _Phrase(
                        "description",
                        start,
                        start + len(words),
                        view.quote(start, start + len(words)),
                    )
                )
        matches = self.matcher.match_many([p.text for p in phrases]) if phrases else []
        hits = []
        for phrase, match in zip(phrases, matches, strict=True):
            if match.matched_skill is not None and match.decision != "no_match":
                hit = self._from_match(phrase, view, match, "llm")
                hits.append(replace(hit, llm=hit.llm or provenance))
        return hits

    # ------------------------------------------------------------------ finishing
    def _with_proficiency(self, hit: SkillHit, views: dict[str, TextView]) -> SkillHit:
        if hit.field is None or hit.span is None:
            return hit
        view = views[hit.field]
        first = next(i for i, t in enumerate(view.tokens) if t.start == hit.span[0])
        end = next(i for i, t in enumerate(view.tokens) if t.end == hit.span[1]) + 1
        cue = self.cues.clause_proficiency(view, first, end)
        if cue is None:
            cue = self.cues.posting_proficiency(views["description"])
        if cue is None:
            return hit
        return replace(hit, proficiency=cue.level, proficiency_cue=cue)

    @staticmethod
    def _merge(hits: list[SkillHit]) -> list[SkillHit]:
        """One hit per skill: accepted before review, then the most confident, then the
        earliest; `mentions` counts how often the skill was found."""
        best: dict[uuid.UUID, SkillHit] = {}
        counts: dict[uuid.UUID, int] = {}
        for hit in hits:
            counts[hit.skill.id] = counts.get(hit.skill.id, 0) + 1
            current = best.get(hit.skill.id)
            key = (hit.decision == MatchDecision.ACCEPT, hit.confidence)
            if current is None or key > (
                current.decision == MatchDecision.ACCEPT,
                current.confidence,
            ):
                best[hit.skill.id] = hit
        return [replace(h, mentions=counts[h.skill.id]) for h in best.values()]


def _runs(first: int, end: int, covered: set[int]) -> list[tuple[int, int]]:
    """Maximal index ranges within first..end-1 that are not covered."""
    runs, start = [], None
    for i in range(first, end + 1):
        free = i < end and i not in covered
        if free and start is None:
            start = i
        elif not free and start is not None:
            runs.append((start, i))
            start = None
    return runs
