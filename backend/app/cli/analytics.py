"""Demand -> supply -> mismatch for all districts, from the command line (backend/, venv):

    python -m app.cli.analytics run                 # compute + store a pipeline run + summary
    python -m app.cli.analytics show --district MH-NASHIK [--role ev-service-technician] [--json]
    python -m app.cli.analytics validate            # does the engine find the planted patterns?

Results are stored as one pipeline run (the API serves the current run). All numbers built on
synthetic data are labelled as such; openings and supply are ESTIMATES based on the
assumptions in config/scoring.yaml.
"""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy.exc import OperationalError

from app.config import ConfigError, ProductConfig, load_config


def _config() -> ProductConfig:
    try:
        return load_config()
    except ConfigError as exc:
        print(f"Configuration is invalid:\n{exc}", file=sys.stderr)
        raise SystemExit(1) from None


def _district_table(item: dict) -> None:
    print(
        f"\n{item['district']['name']} ({item['district']['code']}), {item['quarter']}: "
        "district mismatch "
        f"{item['mismatch_score']} (0 = balanced), {item['status_counts']}  [{item['data_label']}]"
    )
    print(f"  {'role':34} {'demand':>6} {'supply/yr':>9} {'openings/yr':>11} {'ratio':>6}  status")
    for role in item["roles"]:
        ratio = "-" if role["ratio"] is None else f"{role['ratio']:.2f}"
        demand = "-" if role["demand_score"] is None else f"{role['demand_score']:.0f}"
        print(
            f"  {role['role']['title']:34} {demand:>6} {role['supply']:>9.0f} "
            f"{role['estimated_openings']:>11.0f} {ratio:>6}  {role['status']}"
        )


def _explain(item: dict) -> None:
    print(
        f"\n{item['district']['name']} - {item['role']['title']} ({item['quarter']})  "
        f"[{item['data_label']}]"
    )
    demand = "-" if item["demand_score"] is None else f"{item['demand_score']:.0f}"
    ratio = "-" if item["ratio"] is None else f"{item['ratio']:.2f}"
    print(
        f"  Demand: {demand}   Supply: {item['supply']:.0f}/yr   Openings (estimate): "
        f"{item['estimated_openings']:.0f}/yr   Ratio: {ratio}   Status: {item['status']}   "
        f"Confidence: {item['confidence']}"
    )
    print("  Reasons:")
    for reason in item["reasons"]:
        flag = " [synthetic evidence]" if reason["is_synthetic"] else ""
        print(f"    - {reason['text']}{flag}")
    print("  Assumptions:")
    for assumption in item["assumptions"]:
        print(f"    - {assumption['name']}: {assumption['value']}")


def cmd_run(args: argparse.Namespace) -> int:
    from app.analytics.engine import run_engine
    from app.analytics.queries import district_mismatch_item, mismatch_items
    from app.analytics.validation import validate
    from app.core.db import SessionLocal
    from app.models import District

    config = _config()
    with SessionLocal() as db:
        summary = run_engine(db, config)
        db.commit()
        print(
            f"Pipeline run {summary.run_id} ({summary.quarter}): {summary.demand_rows} role "
            "demand, "
            f"{summary.skill_rows} skill demand, {summary.supply_rows} supply and "
            f"{summary.mismatch_rows} mismatch rows stored."
        )
        from app.analytics.queries import current_run

        run = current_run(db)
        districts = {d.code: d for d in db.query(District).all()}
        for code in config.scope.district_codes:
            _district_table(
                district_mismatch_item(db, run, districts[code], summary.quarter, config)
            )
        highlights = [("MH-NASHIK", "ev-service-technician"), ("MH-KOLHAPUR", "wireman")]
        for code, role in highlights:
            for item in mismatch_items(
                db, run, districts=[districts[code].id], quarter=summary.quarter, role=role
            ):
                _explain(item)
    findings = validate(summary.computation, config)
    print("\nPlanted-pattern checks (engine outputs vs the synthetic dataset):")
    for finding in findings:
        print(f"  {'PASS' if finding.passed else 'FAIL'}  {finding.id:26} {finding.message}")
    return 0 if all(f.passed for f in findings) else 1


def cmd_show(args: argparse.Namespace) -> int:
    from app.analytics.queries import current_run, district_mismatch_item, mismatch_items
    from app.core.db import SessionLocal
    from app.models import District

    config = _config()
    with SessionLocal() as db:
        run = current_run(db)
        if run is None:
            print("No results yet. Run: python -m app.cli.analytics run", file=sys.stderr)
            return 1
        district = db.query(District).filter(District.code == args.district).one_or_none()
        if district is None:
            print(f"No district {args.district}", file=sys.stderr)
            return 1
        quarter = args.quarter or run.quarter
        if args.role:
            items = mismatch_items(
                db,
                run,
                districts=[district.id],
                quarter=quarter,
                role=args.role,
                include_insufficient=True,
            )
            if args.json:
                print(json.dumps(items, ensure_ascii=False, indent=2, default=str))
            for item in [] if args.json else items:
                _explain(item)
        else:
            item = district_mismatch_item(db, run, district, quarter, config)
            if args.json:
                print(json.dumps(item, ensure_ascii=False, indent=2, default=str))
            else:
                _district_table(item)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from app.analytics.engine import compute
    from app.analytics.inputs import load_inputs
    from app.analytics.validation import validate
    from app.core.db import SessionLocal

    config = _config()
    with SessionLocal() as db:
        computation = compute(load_inputs(db, config), config)
    findings = validate(computation, config)
    for finding in findings:
        print(f"  {'PASS' if finding.passed else 'FAIL'}  {finding.id:26} {finding.message}")
    ok = all(f.passed for f in findings)
    print("All planted patterns found." if ok else "Some planted patterns were NOT found.")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Demand / supply / mismatch engine")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run", help="compute and store all districts and quarters").set_defaults(
        func=cmd_run
    )
    show = commands.add_parser("show", help="print stored results with explanations")
    show.add_argument("--district", required=True)
    show.add_argument("--role")
    show.add_argument("--quarter")
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=cmd_show)
    commands.add_parser(
        "validate", help="check the planted patterns (nothing stored)"
    ).set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        return args.func(args)
    except OperationalError as exc:
        print(
            f"Cannot reach the database. Start it with: docker compose up -d db\n({exc.orig})",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
