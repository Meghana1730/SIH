"""Shared test helpers (not fixtures)."""

import math
import zlib

from app.models import EMBEDDING_DIM
from app.nlp.text import normalize_text


class FakeEmbedder:
    """Bag-of-words vectors: phrases sharing words point in similar directions.
    SYNONYMS map a word onto another to imitate meaning (e.g. "troubleshooting" means
    "diagnostics"). No model download, fully deterministic."""

    model_name = "fake-bag-of-words"
    dimension = EMBEDDING_DIM
    space = "fake-bag-of-words"
    SYNONYMS = {"troubleshooting": "diagnostics"}

    def __init__(self, synonyms: dict[str, str] | None = None) -> None:
        self.synonyms = {**self.SYNONYMS, **(synonyms or {})}

    def _vector(self, text: str) -> list[float]:
        values = [0.0] * self.dimension
        for word in normalize_text(text).split():
            word = self.synonyms.get(word, word)
            values[zlib.crc32(word.encode()) % self.dimension] += 1.0
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def embed_queries(self, texts):
        return [self._vector(t) for t in texts]

    embed_documents = embed_queries
