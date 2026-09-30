"""Measure the skill matcher on data/gold/skill_matching_cases.yaml.

    python -m app.cli.eval_skill_matching                     # model from config/llm.yaml
    python -m app.cli.eval_skill_matching --no-embeddings     # exact/alias/fuzzy only
    python -m app.cli.eval_skill_matching --model-dir models/<other> --model <hf-id> \
        --query-prefix "" --document-prefix "" --floor 0.3    # try another model

Runs in the scratch database (<db>_test) inside a transaction that is rolled back, so no
data is left behind. Prints a Markdown report (save it with --out report.md).
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import ConfigError, load_config
from app.config.loader import ProductConfig
from app.core.scratch_db import prepare_scratch_database
from app.core.settings import REPO_ROOT
from app.nlp.embeddings import EmbeddingUnavailable, SentenceTransformerEmbedder
from app.nlp.evaluation import (
    DEFAULT_CASES_FILE,
    evaluate,
    format_report,
    load_eval_set,
    seed_vocabulary,
)
from app.nlp.skill_embeddings import embed_vocabulary
from app.nlp.skill_matcher import SkillMatcher


def _with_overrides(config: ProductConfig, args: argparse.Namespace) -> ProductConfig:
    changes = {
        key: value
        for key, value in {
            "model_name": args.model,
            "local_path": args.model_dir,
            "query_prefix": args.query_prefix,
            "document_prefix": args.document_prefix,
            "similarity_floor": args.floor,
        }.items()
        if value is not None
    }
    if not changes:
        return config
    embeddings = config.llm.embeddings.model_copy(update=changes)
    llm = config.llm.model_copy(update={"embeddings": embeddings})
    return ProductConfig(**{**config.__dict__, "llm": llm})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate skill matching.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_FILE)
    parser.add_argument("--no-embeddings", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--model-dir")
    parser.add_argument("--query-prefix")
    parser.add_argument("--document-prefix")
    parser.add_argument("--floor", type=float)
    parser.add_argument("--out", type=Path, help="also write the report to this file")
    args = parser.parse_args(argv)

    try:
        config = _with_overrides(load_config(), args)
    except ConfigError as error:
        print(f"Configuration is invalid:\n{error}", file=sys.stderr)
        return 1
    settings = config.llm.embeddings
    embedder = None
    if not args.no_embeddings:
        embedder = SentenceTransformerEmbedder(settings, config.embedding_model_dir)

    vocabulary, cases = load_eval_set(args.cases)
    engine = create_engine(prepare_scratch_database())
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            db = Session(bind=connection, join_transaction_mode="create_savepoint")
            seed_vocabulary(db, vocabulary, source_ref=str(args.cases))
            if embedder is not None:
                try:
                    embed_vocabulary(db, embedder)
                except EmbeddingUnavailable as error:
                    print(f"{error}\n(Use --no-embeddings to evaluate without them.)")
                    return 1
            outcomes = evaluate(SkillMatcher(db, config, embedder), cases)
        finally:
            transaction.rollback()  # leave nothing behind
    engine.dispose()

    title = (
        f"Skill matching: {settings.model_name} (floor {settings.similarity_floor})"
        if embedder
        else "Skill matching: exact / alias / fuzzy only (no embeddings)"
    )
    report = format_report(outcomes, title)
    print(report)
    if args.out:
        out = args.out if args.out.is_absolute() else REPO_ROOT / args.out
        out.write_text(report + "\n", encoding="utf-8")
        print(f"\nReport written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
