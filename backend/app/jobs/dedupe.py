"""The duplicate-posting key (job_posting.dedupe_key), shared by CSV ingestion and the
synthetic generator: the same ad from the same employer in the same district and ISO week
counts once, however its title is capitalised or punctuated."""

import hashlib
from datetime import date

from app.nlp.text import normalize_text


def posting_dedupe_key(title: str, employer: str | None, district_key: str, posted_on: date) -> str:
    """district_key: the district code, or a stand-in for an ad whose district is unknown."""
    week = "{}-W{:02d}".format(*posted_on.isocalendar()[:2])
    parts = (normalize_text(title), normalize_text(employer or ""), district_key, week)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
