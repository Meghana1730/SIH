"""The job intelligence pipeline from the command line (backend/, venv active):

    python -m app.cli.jobs ingest [data/raw/job_postings.csv] [--no-process]
    python -m app.cli.jobs process [--limit 100] [--retry-failed]     # batch: PENDING postings
    python -m app.cli.jobs show <posting-id> [--dry-run]              # stored links + evidence
    python -m app.cli.jobs try --title "EV Technician" --description "..."   # nothing stored
    python -m app.cli.jobs evaluate [--no-embeddings] [--llm] [--synthetic 300] [--out FILE]

`evaluate` runs in the scratch database (<db>_test) inside a transaction that is rolled
back: it loads only the demo vocabulary there, so the development database is untouched.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import ConfigError, ProductConfig, load_config
from app.core.settings import REPO_ROOT

DEFAULT_CSV = REPO_ROOT / "data" / "raw" / "job_postings.csv"
SAMPLE_CSV = REPO_ROOT / "data" / "synthetic" / "job_postings_sample.csv"
VOCABULARY_TABLES = ("skill", "skill_alias", "job_role", "role_skill")


class CliError(Exception):
    pass


def _config() -> ProductConfig:
    try:
        return load_config()
    except ConfigError as exc:
        raise CliError(f"Configuration is invalid:\n{exc}") from exc


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


# --------------------------------------------------------------------------- commands
def cmd_ingest(args: argparse.Namespace) -> int:
    from app.core.db import SessionLocal
    from app.jobs.ingest import ingest_postings_csv
    from app.jobs.processing import JobIntelligence, process_batch

    config = _config()
    path = Path(args.path).resolve() if args.path else DEFAULT_CSV
    if not path.is_file():
        hint = (
            f"\nTry the synthetic sample: copy {SAMPLE_CSV.relative_to(REPO_ROOT)} "
            f"to {DEFAULT_CSV.relative_to(REPO_ROOT)}"
            if path == DEFAULT_CSV
            else ""
        )
        raise CliError(f"No file {path}.{hint}")
    name = path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else path.name
    with SessionLocal() as db:
        report = ingest_postings_csv(
            db, config, path.read_bytes(), file_name=name, default_source=args.default_source
        )
        db.commit()
        if not args.no_process and report.posting_ids:
            batch = process_batch(
                db,
                JobIntelligence.create(db, config),
                limit=len(report.posting_ids),
                posting_ids=report.posting_ids,
            )
            report.processed, report.failed = batch.processed, batch.failed
            report.skills_extracted, report.roles_matched = (
                batch.skills_extracted,
                batch.roles_matched,
            )
            report.review_items, report.llm_calls = batch.review_items, batch.llm_calls
    out = report.to_dict()
    print(
        f"{name}: {out['records_seen']} rows seen, {out['records_imported']} imported, "
        f"{out['duplicates']} duplicates, {out['errors']} errors; "
        f"{out['skills_extracted']} skills extracted, {out['roles_matched']} roles matched "
        f"({out['processed']} processed, {out['failed']} failed, "
        f"{out['review_items']} review items, {out['llm_calls']} LLM calls)."
    )
    for label, key in (
        ("Duplicate", "duplicate_rows"),
        ("Error", "error_rows"),
        ("Warning", "warning_rows"),
    ):
        for note in out[key]:
            where = f"{note['field']}: " if note["field"] else ""
            print(f"  {label} row {note['row']}: {where}{note['message']}")
    return 0 if out["records_seen"] and not (out["errors"] and not out["records_imported"]) else 1


def cmd_process(args: argparse.Namespace) -> int:
    from app.core.db import SessionLocal
    from app.jobs.processing import JobIntelligence, process_batch

    config = _config()
    with SessionLocal() as db:
        report = process_batch(
            db, JobIntelligence.create(db, config), limit=args.limit, retry_failed=args.retry_failed
        )
    print(
        f"Processed {report.processed} of {report.selected} postings ({report.failed} failed): "
        f"{report.skills_extracted} observed skills, {report.roles_matched} roles, "
        f"{report.review_items} review items, {report.llm_calls} LLM calls. "
        f"{report.remaining} still waiting."
    )
    for failure in report.failures:
        print(f"  FAILED {failure['posting_id']}: {failure['error']}")
    return 0 if not report.failed else 1


def cmd_show(args: argparse.Namespace) -> int:
    import uuid

    from app.core.db import SessionLocal
    from app.jobs.processing import (
        GroundTruthConflict,
        JobIntelligence,
        analysis_out,
        posting_out,
        process_posting,
    )
    from app.models import JobPosting

    config = _config()
    with SessionLocal() as db:
        posting = db.get(JobPosting, uuid.UUID(args.posting_id))
        if posting is None:
            raise CliError(f"No job posting {args.posting_id}")
        if args.dry_run:
            try:
                result = process_posting(
                    db, JobIntelligence.create(db, config), posting, dry_run=True
                )
            except GroundTruthConflict as exc:  # pragma: no cover - dry runs never conflict
                raise CliError(str(exc)) from exc
            assert result.analysis is not None
            _print_json(
                {
                    "posting_id": str(posting.id),
                    "stored": False,
                    **analysis_out(result.analysis, posting),
                }
            )
            db.rollback()
        else:
            _print_json(posting_out(db, posting))
    return 0


def cmd_try(args: argparse.Namespace) -> int:
    from app.core.db import SessionLocal
    from app.jobs.processing import JobIntelligence, analysis_out

    config = _config()
    with SessionLocal() as db:
        analysis = JobIntelligence.create(db, config).analyze(
            args.title, args.description, args.sector
        )
        _print_json(analysis_out(analysis))
        db.rollback()  # keep nothing (not even LLM cache entries)
    return 0


def vocabulary_only(dataset: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """The export with everything except the skill/role vocabulary emptied."""
    return {
        name: rows if name in (*VOCABULARY_TABLES, "sector", "district") else []
        for name, rows in dataset.items()
    }


def cmd_evaluate(args: argparse.Namespace) -> int:
    from app.core.scratch_db import prepare_scratch_database
    from app.jobs.evaluation import evaluate_gold, evaluate_synthetic, format_report, load_gold
    from app.jobs.processing import JobIntelligence
    from app.llm import create_llm_client
    from app.nlp.embeddings import EmbeddingUnavailable, get_embedder
    from app.nlp.skill_embeddings import embed_vocabulary
    from app.synthetic.export import read_export
    from app.synthetic.loader import load_dataset

    config = _config()
    gold = load_gold(Path(args.gold)) if args.gold else load_gold()
    dataset, _ = read_export(REPO_ROOT / config.synthetic.export_dir, config)
    engine = create_engine(prepare_scratch_database())
    notes = []
    with engine.connect() as connection:
        transaction = connection.begin()
        db = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            load_dataset(db, vocabulary_only(dataset), config)
            embedder = None if args.no_embeddings else get_embedder(config)
            if embedder is not None:
                try:
                    embed_vocabulary(db, embedder)
                except EmbeddingUnavailable as exc:
                    notes.append(f"embeddings unavailable ({exc}); evaluated without them")
                    embedder = None
            llm = create_llm_client(config, db=db) if args.llm else None
            intel = JobIntelligence(db, config, embedder=embedder, llm=llm)
            settings = {
                "embeddings": embedder.model_name if embedder else "off",
                "LLM": f"{llm.provider} ({llm.model})" if llm else "off",
                "scoring config": config.scoring.version,
            }
            parts = ["## Evaluation results", "", *(f"> {n}" for n in notes)]
            parts.append(format_report(evaluate_gold(intel, gold, settings)))
            if args.synthetic:
                synthetic = evaluate_synthetic(intel, dataset, args.synthetic, settings)
                parts.append(
                    "Synthetic ads are written from the vocabulary's own names and aliases, so "
                    "this score is OPTIMISTIC; it checks that nothing is broken, not "
                    "real-world quality.\n"
                )
                parts.append(format_report(synthetic, details=False))
        finally:
            db.close()
            transaction.rollback()
    engine.dispose()
    text = "\n".join(parts)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Report written to {args.out}")
    print(text)
    return 0


# --------------------------------------------------------------------------- entry point
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Job intelligence pipeline")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="import a CSV of job postings")
    ingest.add_argument(
        "path", nargs="?", help=f"CSV file (default {DEFAULT_CSV.relative_to(REPO_ROOT)})"
    )
    ingest.add_argument("--no-process", action="store_true", help="only import (leave PENDING)")
    ingest.add_argument("--default-source", help="source ID for rows without one")
    ingest.set_defaults(func=cmd_ingest)

    process = commands.add_parser("process", help="process PENDING postings in a batch")
    process.add_argument("--limit", type=int, default=100)
    process.add_argument("--retry-failed", action="store_true")
    process.set_defaults(func=cmd_process)

    show = commands.add_parser("show", help="a posting with its skills, role and evidence")
    show.add_argument("posting_id")
    show.add_argument("--dry-run", action="store_true", help="run the pipeline now, store nothing")
    show.set_defaults(func=cmd_show)

    try_parser = commands.add_parser("try", help="analyse a text without storing it")
    try_parser.add_argument("--title", required=True)
    try_parser.add_argument("--description")
    try_parser.add_argument("--sector")
    try_parser.set_defaults(func=cmd_try)

    evaluate = commands.add_parser("evaluate", help="precision/recall on the gold set")
    evaluate.add_argument("--no-embeddings", action="store_true")
    evaluate.add_argument("--llm", action="store_true", help="use the LLM configured in llm.yaml")
    evaluate.add_argument(
        "--synthetic", type=int, default=0, help="also score N synthetic postings"
    )
    evaluate.add_argument("--gold", help="another gold file")
    evaluate.add_argument("--out", help="also write the report to this file")
    evaluate.set_defaults(func=cmd_evaluate)

    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        return args.func(args)
    except CliError as exc:
        print(exc, file=sys.stderr)
        return 1
    except OperationalError as exc:
        print(
            f"Cannot reach the database. Start it with: docker compose up -d db\n({exc.orig})",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
