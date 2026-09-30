"""Synthetic (demo) data: generate, export, load into the database and validate.

Run from backend/ with the venv active:

    python -m app.cli.synthetic all                  # generate + load + validate (usual)
    python -m app.cli.synthetic generate [--seed N]  # write data/synthetic/export/*.csv
    python -m app.cli.synthetic load                 # import the export into the database
    python -m app.cli.synthetic validate             # check the patterns in the database
    python -m app.cli.synthetic validate --source export   # ... or in the CSV export
    python -m app.cli.synthetic check-spec           # only check the world spec file

The seed comes from config/synthetic.yaml (or SYNTH_SEED); --seed overrides it. Everything
generated is marked is_synthetic = true and is NOT official data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy.exc import OperationalError

from app.config import ConfigError, ProductConfig, load_config
from app.core.settings import REPO_ROOT
from app.synthetic.checks import CheckResult, dataset_summary, run_checks
from app.synthetic.export import ExportError, read_export, spec_digest, staleness, write_export
from app.synthetic.generator import GenerationError, generate
from app.synthetic.loader import (
    LoadError,
    differences,
    load_dataset,
    read_dataset,
    unmarked_rows,
)
from app.synthetic.spec import SpecError, WorldSpec, check_spec_against_config, load_spec


class CliError(Exception):
    pass


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _display(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _setup() -> tuple[ProductConfig, WorldSpec, Path]:
    try:
        config = load_config()
    except ConfigError as exc:
        raise CliError(f"Configuration is invalid:\n{exc}") from exc
    spec_path = _repo_path(config.synthetic.spec_file)
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        raise CliError(str(exc)) from exc
    problems = check_spec_against_config(spec, config)
    if problems:
        raise CliError(
            f"{_display(spec_path)} does not fit config/*.yaml:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )
    return config, spec, spec_path


def _export_dir(config: ProductConfig, value: str | None) -> Path:
    """--out/--from as typed (relative to the current folder), else export_dir from config
    (relative to the repository root)."""
    return Path(value).resolve() if value else _repo_path(config.synthetic.export_dir)


def _print_results(results: list[CheckResult], verbose: bool) -> bool:
    for result in results:
        print(f"  {result.status:4}  {result.id:7} {result.title}")
        if verbose or result.passed is False:
            for line in result.details:
                if verbose or "[FAIL]" in line:
                    print(f"              {line}")
    ok = all(r.passed is not False for r in results)
    failed = [r.id for r in results if r.passed is False]
    print("All checks passed." if ok else f"FAILED checks: {', '.join(failed)}")
    return ok


# --------------------------------------------------------------------------- commands
def cmd_check_spec(args: argparse.Namespace) -> int:
    config, spec, spec_path = _setup()
    postings = sum(sum(c) for s in spec.posting_schedule.values() for c in s.values())
    print(
        f"OK: {_display(spec_path)} is valid ({len(spec.skills)} skills, {len(spec.roles)} "
        f"roles, {len(spec.courses)} courses, {len(spec.institutes)} institutes, "
        f"{len(spec.employers)} employers, {postings} postings planned)."
    )
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    config, spec, spec_path = _setup()
    seed = config.synthetic.seed if args.seed is None else args.seed
    try:
        dataset = generate(config, spec, seed=seed)
    except GenerationError as exc:
        raise CliError(f"Generation failed: {exc}") from exc
    results = run_checks(dataset, config, spec)
    directory = _export_dir(config, args.out)
    try:
        written = write_export(
            dataset,
            directory,
            config,
            seed=seed,
            spec_file=config.synthetic.spec_file,
            spec_sha256=spec_digest(spec_path),
            generated_at=spec.generated_at,
            as_of=spec.as_of,
            summary=dataset_summary(dataset, config, results),
        )
    except ExportError as exc:
        raise CliError(str(exc)) from exc
    except OSError as exc:
        raise CliError(
            f"Cannot write the export in {directory}: {exc}. Is one of its files open (e.g. in "
            "Excel)? Close it and run generate again."
        ) from exc
    rows = sum(len(dataset[t]) for t in dataset if t not in ("sector", "district"))
    print(f"Generated {rows} synthetic rows with seed {seed} -> {_display(directory)}/")
    print(
        f"  {len(written)} files: one CSV per table (job_posting.csv has "
        f"{len(dataset['job_posting'])} rows), manifest.json, summary.json"
    )
    print("Checks on the generated data:")
    return 0 if _print_results(results, args.verbose) else 1


def cmd_load(args: argparse.Namespace) -> int:
    config, spec, spec_path = _setup()
    directory = _export_dir(config, args.source_dir)
    try:
        dataset, manifest = read_export(directory, config)
    except ExportError as exc:
        raise CliError(str(exc)) from exc
    outdated = staleness(manifest, spec_path)
    if outdated and not args.force:
        raise CliError(
            f"The export in {_display(directory)}/ is out of date ({'; '.join(outdated)}). "
            "Regenerate it first (python -m app.cli.synthetic generate), or use --force."
        )
    results = run_checks(dataset, config, spec)
    if not all(r.passed is not False for r in results) and not args.force:
        _print_results(results, verbose=False)
        raise CliError(
            "The export does not pass validation; not loading it (use --force to load anyway)."
        )
    from app.core.db import SessionLocal  # imported late: only this command needs the DB

    files = {entry["table"]: entry["file"] for entry in manifest["files"]}
    with SessionLocal() as db:
        try:
            report = load_dataset(db, dataset, config, file_names=files)
            db.commit()
        except LoadError as exc:
            db.rollback()
            raise CliError(str(exc)) from exc
    written = sum(report.written.values())
    stale = sum(n for t, n in report.deleted.items() if t not in _link_tables())
    created = sum(report.reference_created.values())
    print(
        f"Loaded {written} synthetic rows (seed {manifest['seed']}) from {_display(directory)}/ "
        f"into the database; {stale} stale synthetic rows removed; {created} config "
        f"sectors/districts created."
    )
    print(f"  Ingestion runs: {', '.join(sorted(report.runs))}")
    return 0


def _link_tables() -> set[str]:
    from app.synthetic.tables import SYNTHETIC_TABLES

    return {t.name for t in SYNTHETIC_TABLES if t.is_link}


def _freshness(manifest: dict, spec_path: Path) -> CheckResult:
    outdated = staleness(manifest, spec_path)
    return CheckResult(
        "EXPORT-1",
        "The export was generated from the current spec and generator",
        not outdated,
        [f"[FAIL] {p}" for p in outdated] or ["[ok] spec hash and generator version match"],
    )


def cmd_validate(args: argparse.Namespace) -> int:
    config, spec, spec_path = _setup()
    directory = _export_dir(config, args.source_dir)
    if args.source == "export":
        try:
            dataset, manifest = read_export(directory, config)
        except ExportError as exc:
            raise CliError(str(exc)) from exc
        print(f"Validating the export in {_display(directory)}/ (seed {manifest['seed']}):")
        results = [*run_checks(dataset, config, spec), _freshness(manifest, spec_path)]
        return 0 if _print_results(results, args.verbose) else 1

    from app.core.db import SessionLocal

    with SessionLocal() as db:
        dataset = read_dataset(db, config)
        unmarked = {t: n for t, n in unmarked_rows(db, config).items() if n}
    if not dataset["job_posting"]:
        raise CliError(
            "No synthetic data in the database. Load it first: python -m app.cli.synthetic load"
        )
    results = run_checks(dataset, config, spec)
    # The flag check above only sees flagged rows; ask the database for unflagged ones too.
    results.append(
        CheckResult(
            "DB-2",
            "No row from a synthetic source is missing its is_synthetic flag",
            not unmarked,
            [f"[FAIL] {t}: {n} rows with is_synthetic not true" for t, n in unmarked.items()]
            or ["[ok] every row from Y-sources (and every link of one) is flagged"],
        )
    )
    # The database must hold exactly what the (up-to-date) export describes.
    try:
        exported, manifest = read_export(directory, config)
        problems = differences(exported, dataset)
        results.append(
            CheckResult(
                "DB-1",
                f"Database matches the export (seed {manifest['seed']})",
                not problems,
                [f"[FAIL] {p}" for p in problems]
                or ["[ok] every synthetic row equals its export row"],
            )
        )
        results.append(_freshness(manifest, spec_path))
    except ExportError as exc:
        results.append(CheckResult("DB-1", "Database matches the export", False, [f"[FAIL] {exc}"]))
    print("Validating the synthetic data in the database:")
    return 0 if _print_results(results, args.verbose) else 1


def cmd_all(args: argparse.Namespace) -> int:
    for step in (cmd_generate, cmd_load, cmd_validate):
        code = step(args)
        if code != 0:
            return code
        print()
    return 0


# --------------------------------------------------------------------------- entry point
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic demo data (never official statistics).")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("check-spec", help="validate the world spec file").set_defaults(
        func=cmd_check_spec
    )
    generate_parser = commands.add_parser("generate", help="write the CSV/JSON export")
    load_parser = commands.add_parser("load", help="import the export into the database")
    validate_parser = commands.add_parser(
        "validate", help="check honesty rules and planted patterns"
    )
    all_parser = commands.add_parser("all", help="generate + load + validate")
    for sub in (generate_parser, all_parser):
        sub.add_argument("--seed", type=int, help="override the seed in config/synthetic.yaml")
        sub.add_argument(
            "--out", help="export folder (default: export_dir in config/synthetic.yaml)"
        )
    for sub in (load_parser, validate_parser):
        sub.add_argument("--from", dest="source_dir", help="export folder to read")
    load_parser.add_argument(
        "--force",
        action="store_true",
        help="load even if the export fails validation or is out of date",
    )
    validate_parser.add_argument("--source", choices=["db", "export"], default="db")
    for sub in (generate_parser, validate_parser, all_parser):
        sub.add_argument("-v", "--verbose", action="store_true", help="show every check's evidence")
    generate_parser.set_defaults(func=cmd_generate)
    load_parser.set_defaults(func=cmd_load)
    validate_parser.set_defaults(func=cmd_validate)
    all_parser.set_defaults(func=cmd_all)

    args = parser.parse_args(argv)
    if args.command == "all":
        # "all" loads and validates exactly what it has just generated.
        args.source_dir, args.source, args.force = args.out, "db", False
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # never crash on a console without UTF-8
    try:
        return args.func(args)
    except CliError as exc:
        print(exc, file=sys.stderr)
        return 1
    except OperationalError as exc:
        print(
            "Cannot reach the database. Start it with: docker compose up -d db\n" f"({exc.orig})",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
