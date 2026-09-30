"""Compute embeddings for the skill vocabulary in the database (skill names + aliases).

    python -m app.cli.embed_skills            # only skills/aliases without a current vector
    python -m app.cli.embed_skills --all      # recompute everything (e.g. after a model change)

Needs embeddings enabled in config/llm.yaml (or EMBEDDINGS_ENABLED=true) and the model
downloaded (python -m app.cli.download_embedding_model).
"""

import argparse
import sys

from app.config import ConfigError, load_config
from app.core.db import SessionLocal
from app.nlp.embeddings import EmbeddingUnavailable, get_embedder
from app.nlp.skill_embeddings import embed_vocabulary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed skill names and aliases.")
    parser.add_argument("--all", action="store_true", help="recompute every vector")
    args = parser.parse_args(argv)
    try:
        embedder = get_embedder(load_config())
    except ConfigError as error:
        print(f"Configuration is invalid:\n{error}", file=sys.stderr)
        return 1
    if embedder is None:
        print("Embeddings are switched off (config/llm.yaml or EMBEDDINGS_ENABLED).")
        return 1
    with SessionLocal() as db:
        try:
            report = embed_vocabulary(db, embedder, refresh=args.all)
        except EmbeddingUnavailable as error:
            print(error, file=sys.stderr)
            return 1
        db.commit()
    print(f"Embedded {report.skills} skills and {report.aliases} aliases ({embedder.space}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
