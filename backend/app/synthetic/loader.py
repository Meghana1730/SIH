"""Import the synthetic dataset into PostgreSQL, and read it back.

    report = load_dataset(db, dataset, config)   # the caller commits
    dataset = read_dataset(db, config)           # what is in the database now

Loading is idempotent and safe to repeat:
* Sector and district rows come from config. They are created only if missing; existing
  rows (e.g. with verified official codes) are never changed, and synthetic rows are
  pointed at them.
* Synthetic rows are upserted by their deterministic IDs, so a demo login or validation
  vote that points at "Example ITI A" keeps working after a reload. Synthetic rows from our
  sources that are no longer in the dataset are deleted; link rows are replaced.
* Nothing that is not synthetic is ever changed. Loading stops before changing anything
  if real (non-synthetic) data already uses a code or name the demo data needs, or if
  real data (a login, a vote, a processed real job ad, a computed score ...) still points
  at a synthetic row that would be deleted.
* When a skill's name or an alias text changes, its stored embedding is cleared (it
  described the old text); run python -m app.cli.embed_skills afterwards.
* Every load writes one ingestion_run per source ID, and every row points to its run.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import (
    Table,
    Text,
    cast,
    delete,
    func,
    literal,
    select,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import ProductConfig
from app.models import Base, IngestionRun
from app.models.enums import RunStatus
from app.synthetic.generator import Dataset
from app.synthetic.tables import (
    BY_NAME,
    REFERENCE_TABLES,
    SYNTHETIC_TABLES,
    SyntheticTable,
    columns,
)

# Unique values (besides the primary key) that real data could also use.
NATURAL_KEYS: dict[str, list[tuple[str, ...]]] = {
    "skill": [("code",), ("name",)],
    "skill_alias": [("language", "alias_normalized")],
    "job_role": [("code",)],
    "course": [("code",)],
    "equipment": [("code",)],
    "institute": [("code",)],
    "employer": [("code",)],
    "candidate": [("pseudonym",)],
    "job_posting": [("dedupe_key",)],
}
# Unique columns whose value may move to another synthetic row after a spec or seed change
# (e.g. a posting's dedupe key). They are parked on a placeholder before the upsert, so two
# rows swapping values never collide half-way.
MOVABLE_UNIQUE = {"job_posting": "dedupe_key", "skill": "name"}
# Tables with a stored embedding, and the text column the embedding describes.
EMBEDDED_TEXT = {"skill": "name", "skill_alias": "alias"}
_CHUNK = 5000


class LoadError(Exception):
    """The dataset cannot be loaded without touching real (non-synthetic) data."""


@dataclass
class LoadReport:
    written: dict[str, int] = field(default_factory=dict)
    deleted: dict[str, int] = field(default_factory=dict)
    reference_created: dict[str, int] = field(default_factory=dict)
    runs: dict[str, uuid.UUID] = field(default_factory=dict)


def synthetic_sources(config: ProductConfig) -> list[str]:
    return sorted(set(config.synthetic.source_ids.model_dump().values()))


def _chunks(values: list[Any]) -> list[list[Any]]:
    return [values[i : i + _CHUNK] for i in range(0, len(values), _CHUNK)] or [[]]


def _scope(info: SyntheticTable, sources: list[str]) -> Any:
    """SQL condition selecting OUR synthetic rows of a table."""
    table = info.table
    if info.has_source:
        return table.c.is_synthetic.is_(True) & table.c.source.in_(sources)
    fk, parent_name = info.parent or ("", "")
    parent = Base.metadata.tables[parent_name]
    ours = select(parent.c.id).where(parent.c.is_synthetic.is_(True), parent.c.source.in_(sources))
    return table.c.is_synthetic.is_(True) & table.c[fk].in_(ours)


# --------------------------------------------------------------------------- load
def load_dataset(
    db: Session, dataset: Dataset, config: ProductConfig, file_names: dict[str, str] | None = None
) -> LoadReport:
    """Write the dataset into the database (inside the caller's transaction)."""
    sources = synthetic_sources(config)
    report = LoadReport()
    _refuse_collisions(db, dataset, sources)  # before any change
    _refuse_orphaning(db, dataset, sources)
    try:
        remap = _ensure_reference_rows(db, dataset, report)
    except IntegrityError as exc:
        raise LoadError(
            "A configured sector/district clashes with an existing row (same name, other "
            f"code):\n{exc.orig}"
        ) from exc
    tables = {
        info.name: [_remapped(row, remap) for row in dataset[info.name]]
        for info in SYNTHETIC_TABLES
    }

    # One ingestion run per source ID (Y01, Y02, ...).
    by_source: dict[str, list[str]] = {}
    for info in SYNTHETIC_TABLES:
        source = getattr(config.synthetic.source_ids, info.dataset)
        by_source.setdefault(source, []).append((file_names or {}).get(info.name, info.name))
    runs = {
        source: IngestionRun(
            source=source, file_name=", ".join(names), status=RunStatus.RUNNING.value
        )
        for source, names in sorted(by_source.items())
    }
    db.add_all(runs.values())
    db.flush()
    report.runs = {source: run.id for source, run in runs.items()}

    try:
        # Children first: delete what is no longer in the dataset, and all link rows.
        for info in reversed(SYNTHETIC_TABLES):
            table, scope = info.table, _scope(info, sources)
            if info.is_link:
                condition = scope
            else:
                keep = [row["id"] for row in tables[info.name]]
                condition = scope & table.c.id.not_in(keep) if keep else scope
            report.deleted[info.name] = db.execute(delete(table).where(condition)).rowcount
        # A stored vector describes the old text: clear it where the text changes. Decided
        # before the names are parked below (parking would make every name look changed).
        for name, column in EMBEDDED_TEXT.items():
            info = BY_NAME[name]
            current = dict(
                db.execute(
                    select(info.table.c.id, info.table.c[column]).where(_scope(info, sources))
                ).all()
            )
            changed = [
                row["id"]
                for row in tables[name]
                if row["id"] in current and current[row["id"]] != row[column]
            ]
            for chunk in _chunks(changed):
                if chunk:
                    db.execute(
                        update(info.table)
                        .where(info.table.c.id.in_(chunk))
                        .values(embedding=None, embedding_model=None)
                    )
        for name, column in MOVABLE_UNIQUE.items():
            info = BY_NAME[name]
            placeholder = literal("stale-") + cast(info.table.c.id, Text)
            db.execute(
                update(info.table).where(_scope(info, sources)).values({column: placeholder})
            )
        # Parents first: upsert entities by id, insert link rows.
        for info in SYNTHETIC_TABLES:
            rows = tables[info.name]
            if info.has_source:
                rows = [{**row, "ingestion_run_id": runs[row["source"]].id} for row in rows]
            for chunk in _chunks(rows):
                if chunk:
                    db.execute(_write_statement(info), chunk)
            report.written[info.name] = len(rows)
    except IntegrityError as exc:
        raise LoadError(
            "The database refused the synthetic rows (a conflict with existing data):\n"
            f"{exc.orig}"
        ) from exc

    for source, run in runs.items():
        run.rows_loaded = sum(
            report.written[i.name]
            for i in SYNTHETIC_TABLES
            if getattr(config.synthetic.source_ids, i.dataset) == source
        )
        run.status = RunStatus.SUCCEEDED.value
        run.finished_at = func.clock_timestamp()
    db.flush()
    return report


def _write_statement(info: SyntheticTable) -> Any:
    table = info.table
    statement = insert(table)
    if info.is_link:
        return statement  # we deleted our link rows; a conflict means real data is in the way
    keys = {c.name for c in table.primary_key.columns}
    updates = {
        name: statement.excluded[name]
        for name in [*columns(info.name), *(["ingestion_run_id"] if info.has_source else [])]
        if name not in keys
    }
    if "updated_at" in table.c:
        updates["updated_at"] = func.now()
    return statement.on_conflict_do_update(index_elements=sorted(keys), set_=updates)


def _ensure_reference_rows(db: Session, dataset: Dataset, report: LoadReport) -> dict[Any, Any]:
    """Create config sectors/districts if missing; return {generated id: database id}."""
    remap: dict[Any, Any] = {}
    for name in REFERENCE_TABLES:
        table: Table = Base.metadata.tables[name]
        wanted = dataset[name]
        existing = dict(
            db.execute(
                select(table.c.code, table.c.id).where(
                    table.c.code.in_([r["code"] for r in wanted])
                )
            ).all()
        )
        missing = [row for row in wanted if row["code"] not in existing]
        # A row with the same name but another code is a real clash, not something to guess.
        name_clash = [
            f"{row['name']} (config code {row['code']}, database code {code})"
            for row in missing
            for code in db.scalars(select(table.c.code).where(table.c.name == row["name"]))
        ]
        if name_clash:
            raise LoadError(
                f"These {name} rows already exist under another code: {name_clash}. "
                "Use the same code in config/*.yaml, or fix the database row."
            )
        if missing:
            db.execute(insert(table), missing)
        report.reference_created[name] = len(missing)
        for row in wanted:
            remap[row["id"]] = existing.get(row["code"], row["id"])
    return remap


def _remapped(row: dict[str, Any], remap: dict[Any, Any]) -> dict[str, Any]:
    changed = {
        c: remap[row[c]] for c in ("district_id", "sector_id") if c in row and row[c] in remap
    }
    return {**row, **changed} if changed else row


def _refuse_collisions(
    db: Session, tables: dict[str, list[dict[str, Any]]], sources: list[str]
) -> None:
    """Stop if real (non-synthetic) rows already use a code/name the demo data needs."""
    problems: list[str] = []
    for name, keys in NATURAL_KEYS.items():
        info = BY_NAME[name]
        table = info.table
        for key in keys:
            values = sorted({tuple(row[c] for c in key) for row in tables[name]})
            found: list[tuple[Any, ...]] = []
            for chunk in _chunks(values):
                if not chunk:
                    continue
                if len(key) == 1:
                    matches = table.c[key[0]].in_([value for (value,) in chunk])
                else:
                    matches = tuple_(*(table.c[c] for c in key)).in_(chunk)
                found += db.execute(
                    select(*(table.c[c] for c in key)).where(matches, ~_scope(info, sources))
                ).all()
            if found:
                examples = ", ".join("/".join(str(v) for v in row) for row in found[:5])
                problems.append(
                    f"{name}: {len(found)} non-synthetic rows already use the same "
                    f"{'+'.join(key)} (e.g. {examples})"
                )
    if problems:
        raise LoadError(
            "Loading the synthetic dataset would clash with real data, so nothing was changed:\n"
            + "\n".join(f"  - {p}" for p in problems)
            + "\nRename the demo entries in the spec, or remove the conflicting rows."
        )


def _refuse_orphaning(db: Session, dataset: Dataset, sources: list[str]) -> None:
    """Stop if rows that are NOT ours (real data, logins, votes, computed results ...) point
    at synthetic rows this load would delete: deleting them would cascade into (or null
    out) that real data."""
    problems: list[str] = []
    for info in SYNTHETIC_TABLES:
        if info.is_link:
            continue  # nothing points at link rows
        table = info.table
        keep = [row["id"] for row in dataset[info.name]]
        stale = select(table.c.id).where(_scope(info, sources))
        if keep:
            stale = stale.where(table.c.id.not_in(keep))
        for other in Base.metadata.sorted_tables:
            for fk in other.foreign_keys:
                if fk.column.table is not table:
                    continue
                column = fk.parent
                condition = column.in_(stale)
                if other.name in BY_NAME:  # our own rows are deleted with their parent
                    condition = condition & ~_scope(BY_NAME[other.name], sources)
                count = db.scalar(select(func.count()).select_from(other).where(condition))
                if count:
                    problems.append(
                        f"{count} {other.name} row(s) point at {info.name} rows this load "
                        f"would delete ({other.name}.{column.name})"
                    )
    if problems:
        raise LoadError(
            "Loading would delete synthetic rows that other data still uses, so nothing was "
            "changed:\n"
            + "\n".join(f"  - {p}" for p in problems)
            + "\nKeep those entities in the spec, or remove/re-point the rows that use them."
        )


def unmarked_rows(db: Session, config: ProductConfig) -> dict[str, int]:
    """Rows from our synthetic sources (or with a synthetic parent) whose is_synthetic flag
    is not true. read_dataset() cannot see them (it selects flagged rows), so the database
    validation asks for them directly. The answer must be all zeros."""
    sources = synthetic_sources(config)
    counts = {}
    for info in SYNTHETIC_TABLES:
        table = info.table
        if info.has_source:
            ours = table.c.source.in_(sources)
        else:
            fk, parent_name = info.parent or ("", "")
            parent = Base.metadata.tables[parent_name]
            ours = table.c[fk].in_(select(parent.c.id).where(parent.c.source.in_(sources)))
        query = (
            select(func.count()).select_from(table).where(ours, table.c.is_synthetic.is_not(True))
        )
        counts[info.name] = db.scalar(query) or 0
    return counts


# --------------------------------------------------------------------------- read back
def read_dataset(db: Session, config: ProductConfig) -> Dataset:
    """The synthetic dataset as stored in the database (plus the config sectors/districts).
    Rows include ingestion_run_id, so the validator can check it."""
    sources = synthetic_sources(config)
    dataset: Dataset = {}
    codes = {"sector": config.sectors.codes, "district": config.scope.district_codes}
    for name in REFERENCE_TABLES:
        table = Base.metadata.tables[name]
        selected = [table.c[c] for c in columns(name)]
        dataset[name] = [
            dict(row._mapping)
            for row in db.execute(
                select(*selected).where(table.c.code.in_(codes[name])).order_by(table.c.code)
            )
        ]
    for info in SYNTHETIC_TABLES:
        table = info.table
        names = [*columns(info.name), *(["ingestion_run_id"] if info.has_source else [])]
        order = [table.c[c.name] for c in table.primary_key.columns]
        statement = (
            select(*(table.c[c] for c in names)).where(_scope(info, sources)).order_by(*order)
        )
        dataset[info.name] = [dict(row._mapping) for row in db.execute(statement)]
    return dataset


def differences(expected: Dataset, actual: Dataset, limit: int = 10) -> list[str]:
    """Where the database content differs from a generated/exported dataset (after pointing
    the expected rows at the database's own sector/district IDs)."""
    remap = {}
    for name in REFERENCE_TABLES:
        by_code = {r["code"]: r["id"] for r in actual[name]}
        remap.update({r["id"]: by_code.get(r["code"], r["id"]) for r in expected[name]})
    problems: list[str] = []
    for info in SYNTHETIC_TABLES:
        keys = [c.name for c in info.table.primary_key.columns]
        wanted = {tuple(row[k] for k in keys): _remapped(row, remap) for row in expected[info.name]}
        stored = {
            tuple(row[k] for k in keys): {c: v for c, v in row.items() if c != "ingestion_run_id"}
            for row in actual[info.name]
        }
        if len(wanted) != len(stored):
            problems.append(f"{info.name}: expected {len(wanted)} rows, database has {len(stored)}")
        for key, row in wanted.items():
            if len(problems) >= limit:
                return problems
            if stored.get(key) != row:
                other = stored.get(key)
                changed = sorted(c for c in row if other is None or other.get(c) != row[c])
                problems.append(f"{info.name} {key}: differs in {changed}")
    return problems
