"""Language cues for job ads (data/reference/job_text_cues.yaml): connectors, filler words,
skill-context words, requested proficiency, years of experience, Hindi vs Marathi.

Proficiency is what the AD ASKS FOR ("hands-on", "2-4 years"), never a certified level.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.core.settings import REPO_ROOT
from app.models.enums import Language, Proficiency
from app.nlp.text import normalize_text
from app.nlp.tokens import TextView

CUES_FILE = REPO_ROOT / "data" / "reference" / "job_text_cues.yaml"

# "2-4 years", "5+ yrs", "1 to 3 years", "2 वर्ष", "3 वर्षे", "2 साल"
_YEARS = re.compile(
    r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:(?:-|–|to|ते|से)\s*(\d{1,2}(?:\.\d)?)\s*\+?\s*)?"
    r"(?:years?|yrs?|वर्षे|वर्ष|साल)(?![A-Za-z])",
    re.IGNORECASE,
)
# A years expression only counts as experience when an experience word is near it, and not
# when it is an age limit, a bond, or the company's age ("Age 18-35 years", "2 years bond",
# "a 25 years old company").
_EXPERIENCE_WORD = re.compile(r"experience|experienced|\bexp\b|अनुभव", re.IGNORECASE)
_NOT_EXPERIENCE_BEFORE = re.compile(
    r"\bage\b|\baged\b|उम्र|उमर|वय|\bbond\b|since|established|warranty|guarantee",
    re.IGNORECASE,
)
_NOT_EXPERIENCE_AFTER = re.compile(r"\s*(?:old|bond|of age|age)\b", re.IGNORECASE)
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LEVEL_ORDER = (Proficiency.BASIC, Proficiency.INTERMEDIATE, Proficiency.ADVANCED)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Words = dict[Language, list[str]]


class ExperienceYears(_Model):
    basic_max: Annotated[float, Field(ge=0)]
    advanced_min: Annotated[float, Field(gt=0)]


class LanguageMarkers(_Model):
    mr: list[str]
    hi: list[str]
    mr_letters: list[str]


class CueFile(_Model):
    connectors: Words
    filler: Words
    skill_context: Words
    proficiency: dict[Proficiency, Words]
    experience_years: ExperienceYears
    posting_proficiency: dict[Proficiency, Words]
    language_markers: LanguageMarkers


def _phrases(words: Words) -> set[tuple[str, ...]]:
    return {
        tuple(normalize_text(w).split())
        for values in words.values()
        for w in values
        if normalize_text(w)
    }


@dataclass(frozen=True)
class Cue:
    level: Proficiency
    text: str  # the words found in the ad
    source: str  # "clause" | "clause years" | "posting" | "posting years"


class Cues:
    """Normalised, ready-to-match cue sets."""

    def __init__(self, data: CueFile) -> None:
        self.data = data
        self.connectors = {w[0] for w in _phrases(data.connectors) if len(w) == 1}
        self.filler = {w[0] for w in _phrases(data.filler) if len(w) == 1}
        self.skill_context = _phrases(data.skill_context)
        self.levels = {level: _phrases(words) for level, words in data.proficiency.items()}
        self.posting_levels = {
            level: _phrases(words) for level, words in data.posting_proficiency.items()
        }

    # ------------------------------------------------------------------ proficiency
    def years_level(self, low: float, high: float | None) -> Proficiency:
        limits = self.data.experience_years
        if high is not None and high <= limits.basic_max:
            return Proficiency.BASIC
        if low >= limits.advanced_min:
            return Proficiency.ADVANCED
        return Proficiency.INTERMEDIATE

    def clause_proficiency(self, view: TextView, first: int, end: int) -> Cue | None:
        """The level asked for in the clause around tokens first..end-1 (the skill's own
        words are ignored, so "Basic Motor Maintenance" does not read as 'basic')."""
        seg_first, seg_end = view.segment_of(first)
        clause = view.quote(seg_first, seg_end)
        if (years := first_years(clause)) is not None:
            return Cue(self.years_level(*years), years_text(clause) or "", "clause years")
        best: tuple[int, int, Cue] | None = None
        for rank, level in enumerate(LEVEL_ORDER):
            for words in self.levels.get(level, ()):
                for start in view.find(words, seg_first, seg_end):
                    stop = start + len(words)
                    if start < end and stop > first:  # overlaps the skill's own words
                        continue
                    distance = first - stop if stop <= first else start - end
                    key = (distance, -rank)
                    if best is None or key < best[:2]:
                        best = (distance, -rank, Cue(level, view.quote(start, stop), "clause"))
        return best[2] if best else None

    def posting_proficiency(self, view: TextView) -> Cue | None:
        """A level for the whole ad (years of experience, or words like 'fresher')."""
        if (years := first_years(view.text)) is not None:
            return Cue(self.years_level(*years), years_text(view.text) or "", "posting years")
        for level in (Proficiency.ADVANCED, Proficiency.BASIC):
            for words in self.posting_levels.get(level, ()):
                if hits := view.find(words):
                    start = hits[0]
                    return Cue(level, view.quote(start, start + len(words)), "posting")
        return None

    # ------------------------------------------------------------------ context and language
    def has_skill_context(self, view: TextView, first: int, end: int) -> bool:
        """Does the sentence of tokens first..end-1 talk about skills (up to the phrase)?"""
        sent_first, _ = view.sentence_of(first)
        return any(view.find(words, sent_first, end) for words in self.skill_context)

    def detect_language(self, text: str) -> Language:
        if not _DEVANAGARI.search(text or ""):
            return Language.EN
        words = normalize_text(text).split()
        markers = self.data.language_markers
        mr = sum(words.count(w) for w in markers.mr) + sum(
            text.count(c) for c in markers.mr_letters
        )
        hi = sum(words.count(w) for w in markers.hi)
        return Language.MR if mr > hi else Language.HI


def _experience_years(text: str) -> re.Match[str] | None:
    """The first years expression in the text that is about work experience."""
    text = text or ""
    previous_end = 0
    for match in _YEARS.finditer(text):
        before = text[max(previous_end, match.start() - 25) : match.start()]
        previous_end = match.end()
        if _NOT_EXPERIENCE_BEFORE.search(before) or _NOT_EXPERIENCE_AFTER.match(text, match.end()):
            continue
        if _EXPERIENCE_WORD.search(text[max(0, match.start() - 40) : match.end() + 30]):
            return match
    return None


def first_years(text: str) -> tuple[float, float | None] | None:
    match = _experience_years(text)
    if match is None:
        return None
    low = float(match.group(1))
    high = float(match.group(2)) if match.group(2) else None
    return low, high


def years_text(text: str) -> str | None:
    match = _experience_years(text)
    return match.group(0).strip() if match else None


@lru_cache(maxsize=4)
def load_cues(path: Path = CUES_FILE) -> Cues:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Cues(CueFile.model_validate(data))
