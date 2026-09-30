"""Split job-ad text into tokens WITH their positions, so every match can quote its evidence.

The tokens are the same words that `normalize_text` produces (case-folded, punctuation and
symbols removed, Devanagari vowel signs kept), plus the character offsets of each word in the
original (NFC-normalised) text:

    view = analyze_text("EV technician required, with BMS experience.")
    [t.norm for t in view.tokens]  -> ['ev', 'technician', 'required', 'with', 'bms', 'experience']
    view.segments                  -> [(0, 3), (3, 6)]   (split at , ; : . and similar)
    view.quote(4, 5)               -> 'BMS'

Segments are clauses separated by punctuation; sentences are separated by . ! ? । and new
lines only.
"""

import unicodedata
from dataclasses import dataclass, field

# Punctuation that ends a clause (segment). Hyphens, slashes and '&' only separate words.
SEGMENT_BREAKS = set('.,;:!?।॥|•·()[]{}"“”–—\n\r\t')
SENTENCE_BREAKS = set(".!?।॥\n\r")


@dataclass(frozen=True)
class Token:
    norm: str  # case-folded word
    start: int  # character offsets in TextView.text
    end: int


@dataclass(frozen=True)
class TextView:
    text: str  # the NFC-normalised input; offsets refer to it
    tokens: list[Token]
    segments: list[tuple[int, int]]  # token index ranges [start, end)
    sentences: list[tuple[int, int]] = field(default_factory=list)

    @property
    def norms(self) -> list[str]:
        return [t.norm for t in self.tokens]

    def quote(self, first: int, end: int) -> str:
        """Original text covering tokens first..end-1."""
        if first >= end:
            return ""
        return self.text[self.tokens[first].start : self.tokens[end - 1].end]

    def segment_of(self, index: int) -> tuple[int, int]:
        return next((s for s in self.segments if s[0] <= index < s[1]), (index, index + 1))

    def sentence_of(self, index: int) -> tuple[int, int]:
        return next((s for s in self.sentences if s[0] <= index < s[1]), self.segment_of(index))

    def find(self, words: tuple[str, ...], first: int = 0, end: int | None = None) -> list[int]:
        """Start indexes where the word sequence occurs within tokens first..end-1."""
        end = len(self.tokens) if end is None else end
        size = len(words)
        norms = self.norms
        return [i for i in range(first, end - size + 1) if tuple(norms[i : i + size]) == words]


def _is_separator(char: str) -> bool:
    return char.isspace() or unicodedata.category(char)[0] in ("P", "S", "Z")


def analyze_text(text: str | None) -> TextView:
    text = unicodedata.normalize("NFC", text or "")
    tokens: list[Token] = []
    segments: list[tuple[int, int]] = []
    sentences: list[tuple[int, int]] = []
    segment_start = sentence_start = 0
    word_start: int | None = None

    def close(bounds: list[tuple[int, int]], start: int) -> int:
        if len(tokens) > start:
            bounds.append((start, len(tokens)))
        return len(tokens)

    for position, char in enumerate(text):
        if _is_separator(char):
            if word_start is not None:
                tokens.append(Token(text[word_start:position].casefold(), word_start, position))
                word_start = None
            if char in SEGMENT_BREAKS:
                segment_start = close(segments, segment_start)
            if char in SENTENCE_BREAKS:
                sentence_start = close(sentences, sentence_start)
        elif word_start is None:
            word_start = position
    if word_start is not None:
        tokens.append(Token(text[word_start:].casefold(), word_start, len(text)))
    close(segments, segment_start)
    close(sentences, sentence_start)
    return TextView(text, tokens, segments, sentences)
