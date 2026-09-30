"""Map a job ad's district / location text to a district (never by guessing).

Looks for, in order: the district code ("MH-NASHIK"), the district name or a spelling from
config/scope.yaml ("Nashik", "Nasik"), then a known place in that district from
data/reference/place_aliases.yaml ("Ambad MIDC"). If nothing matches, or two districts match,
the district stays empty and the ad goes to the review queue (PLACE_MAPPING).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ProductConfig
from app.core.settings import REPO_ROOT
from app.models import District
from app.nlp.text import normalize_text

PLACES_FILE = REPO_ROOT / "data" / "reference" / "place_aliases.yaml"


@dataclass(frozen=True)
class PlaceMatch:
    district_id: uuid.UUID | None
    code: str | None
    how: str  # "code" | "name" | "place 'Ambad MIDC'" | "not found" | "ambiguous: ..."


class DistrictResolver:
    def __init__(self, db: Session, config: ProductConfig, places_file: Path = PLACES_FILE) -> None:
        self.ids = dict(db.execute(select(District.code, District.id)).all())
        self.names: dict[tuple[str, ...], set[str]] = {}
        for entry in config.scope.districts:
            for text in [entry.name, *entry.aliases]:
                self._add(text, entry.code, self.names)
        for code, name, aliases in db.execute(
            select(District.code, District.name, District.aliases)
        ):
            for text in [name, *(aliases or [])]:
                self._add(text, code, self.names)
        self.places: dict[tuple[str, ...], set[str]] = {}
        if places_file.is_file():
            data = yaml.safe_load(places_file.read_text(encoding="utf-8")) or {}
            for code, names in (data.get("places") or {}).items():
                for text in names:
                    self._add(text, code, self.places)

    @staticmethod
    def _add(text: str, code: str, index: dict[tuple[str, ...], set[str]]) -> None:
        if words := tuple(normalize_text(text).split()):
            index.setdefault(words, set()).add(code)

    def _found(self, code: str, how: str) -> PlaceMatch:
        return (
            PlaceMatch(self.ids.get(code), code, how)
            if code in self.ids
            else PlaceMatch(None, None, f"{how} (district {code} not in the database)")
        )

    def resolve(self, district_text: str | None, location_text: str | None) -> PlaceMatch:
        for text in (district_text, location_text):
            if text and text.strip().upper() in self.ids:
                return self._found(text.strip().upper(), "code")
        for index, label in ((self.names, "name"), (self.places, "place")):
            for text in (district_text, location_text):
                words = normalize_text(text or "").split()
                if not words:
                    continue
                found: dict[str, str] = {}
                for term, codes in sorted(index.items(), key=lambda item: -len(item[0])):
                    size = len(term)
                    if any(
                        tuple(words[i : i + size]) == term for i in range(len(words) - size + 1)
                    ):
                        for code in codes:
                            found.setdefault(code, " ".join(term))
                if len(found) == 1:
                    code, term = next(iter(found.items()))
                    return self._found(code, label if label == "name" else f"place '{term}'")
                if len(found) > 1:
                    return PlaceMatch(None, None, f"ambiguous: {sorted(found)}")
        return PlaceMatch(None, None, "not found")
