"""Text normalisation shared by every matching step (and by data loaders that fill
`skill_alias.alias_normalized`), so "EV-Diagnostics", "ev  diagnostics" and
"EV Diagnostics" all become "ev diagnostics".

Careful with Hindi / Marathi: Devanagari vowel signs (e.g. "ि", "ा") are *combining marks*,
not letters, so a naive "keep only letters and digits" rule would destroy words. We remove
only punctuation and symbols, and keep marks.
"""

import unicodedata


def normalize_text(text: str) -> str:
    # NFC: one standard Unicode form, so visually identical text compares equal.
    text = unicodedata.normalize("NFC", text).casefold()
    cleaned = []
    for char in text:
        category = unicodedata.category(char)
        # P* = punctuation (- / , . ( ) ...), S* = symbols (+ & ...): treat as a space.
        cleaned.append(" " if category[0] in ("P", "S") else char)
    return " ".join("".join(cleaned).split())
