"""Sentence embeddings: turn a phrase into a list of numbers so that phrases with similar
meaning get similar numbers (measured with cosine similarity).

Optional feature (docs/04-architecture.md §4.3):
* needs the `embeddings` extra:  pip install -e ".[embeddings]"
* needs the model files on disk, downloaded ONCE with:
      python -m app.cli.download_embedding_model
* the model is loaded from disk only (never downloaded at runtime) and once per process.
If anything is missing, callers get EmbeddingUnavailable and fall back to fuzzy matching.
"""

import os
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from app.config import ProductConfig
from app.config.llm import EmbeddingSettings

# Files every sentence-transformers model folder contains.
MODEL_MARKER_FILES = ("config.json", "modules.json")


class EmbeddingUnavailable(Exception):
    """Embeddings are switched off, not installed, or the model is not downloaded."""


class Embedder(Protocol):
    """Anything that can embed text (the real model, or a fake one in tests)."""

    model_name: str
    dimension: int
    # Identifies the "vector space": vectors are only comparable if made by the same model
    # with the same text prefix. Stored in skill.embedding_model / skill_alias.embedding_model.
    space: str

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...


def embedding_space(settings: EmbeddingSettings) -> str:
    prefix = settings.document_prefix.strip()
    return f"{settings.model_name}|{prefix}" if prefix else settings.model_name


def model_files_present(model_dir: Path) -> bool:
    return all((model_dir / name).is_file() for name in MODEL_MARKER_FILES)


# Loaded models, by folder: loading takes seconds and ~0.5 GB RAM, so do it once.
_loaded: dict[str, Any] = {}
_lock = threading.Lock()


class SentenceTransformerEmbedder:
    def __init__(self, settings: EmbeddingSettings, model_dir: Path) -> None:
        self.model_name = settings.model_name
        self.dimension = settings.dimension
        self.space = embedding_space(settings)
        self._settings = settings
        self._model_dir = model_dir

    def _model(self) -> Any:
        key = str(self._model_dir.resolve())
        with _lock:
            if key not in _loaded:
                if not model_files_present(self._model_dir):
                    raise EmbeddingUnavailable(
                        f"Embedding model not found in {self._model_dir}. Download it once with:"
                        "\n  python -m app.cli.download_embedding_model"
                    )
                # Belt and braces: never contact the internet when loading.
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError:
                    raise EmbeddingUnavailable(
                        "sentence-transformers is not installed. Run (backend venv active):"
                        '\n  pip install -e ".[embeddings]"'
                    ) from None
                model = SentenceTransformer(key, device="cpu", local_files_only=True)
                # Newer sentence-transformers renamed this method; support both names.
                get_size = (
                    getattr(model, "get_embedding_dimension", None)
                    or model.get_sentence_embedding_dimension
                )
                size = get_size()
                if size != self.dimension:
                    raise EmbeddingUnavailable(
                        f"Model in {self._model_dir} makes {size}-number vectors, but "
                        f"config/llm.yaml says dimension {self.dimension}."
                    )
                _loaded[key] = model
            return _loaded[key]

    def _encode(self, texts: Sequence[str], prefix: str) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model().encode(
            [prefix + text for text in texts],
            batch_size=self._settings.batch_size,
            normalize_embeddings=True,  # unit length: cosine similarity = dot product
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        """For the text we are trying to match (e.g. a phrase from a job ad)."""
        return self._encode(texts, self._settings.query_prefix)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """For the stored vocabulary (skill names and aliases)."""
        return self._encode(texts, self._settings.document_prefix)


def get_embedder(config: ProductConfig) -> Embedder | None:
    """The configured embedder, or None when embeddings are switched off in config."""
    settings = config.llm.embeddings
    if not settings.enabled:
        return None
    return SentenceTransformerEmbedder(settings, config.embedding_model_dir)
