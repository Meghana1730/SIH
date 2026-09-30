"""Import job postings from a CSV file (docs/06-job-intelligence.md §2).

Expected columns (header names are case-insensitive; a few synonyms are accepted):
    title, description, employer, location, district, sector, posted_date,
    source, source_ref, license_note, is_synthetic

Row rules:
* title and a valid posted_date are required (dates: YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY,
  DD.MM.YYYY, "12 Mar 2026"; day first, never in the future).
* A missing description is allowed (skills then come from the title only) with a warning.
* Provenance is kept for every row. `source` is required (or --default-source); a missing
  source_ref becomes "<file> row <n>"; a missing license_note becomes "TODO-VERIFY".
  is_synthetic must agree with the source (Y.. sources are synthetic); if missing it is taken
  from the source prefix.
* Phone numbers and e-mail addresses are removed from the text before storing (privacy).
* The district comes from the district or location text (codes, names, known places); if
  it cannot be found the ad is still imported and a PLACE_MAPPING review item is created.
* Duplicates (same title + employer + district + ISO week, within the file or already in the
  database) are skipped and reported.

Imported postings are PENDING until the pipeline processes them (process_postings).
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import ProductConfig
from app.jobs.dedupe import posting_dedupe_key
from app.jobs.places import DistrictResolver
from app.models import Employer, IngestionRun, JobPosting, ReviewItem, Sector
from app.models.enums import ExtractionStatus, ReviewKind, RunStatus
from app.nlp.cues import first_years, load_cues
from app.nlp.text import normalize_text
from app.synthetic.timeline import quarter_of

COLUMNS = (
    "title",
    "description",
    "employer",
    "location",
    "district",
    "sector",
    "posted_date",
    "source",
    "source_ref",
    "license_note",
    "is_synthetic",
)
REQUIRED = ("title", "posted_date")
SYNONYMS = {
    "job_title": "title",
    "job_description": "description",
    "employer_name": "employer",
    "company": "employer",
    "posted_on": "posted_date",
    "date": "posted_date",
    "source_id": "source",
}
DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y")
EARLIEST_DATE = date(2000, 1, 1)
MAX_ROWS = 20_000
TRUE, FALSE = {"true", "yes", "y", "1", "t"}, {"false", "no", "n", "0", "f"}
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(
    r"(?<![\w/-])(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?![\w/-])|(?<!\d)0\d{2,4}[\s-]\d{6,8}(?!\d)"
)


@dataclass(frozen=True)
class RowNote:
    row: int  # line number in the file (the header is line 1)
    field: str | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"row": self.row, "field": self.field, "message": self.message}


@dataclass
class IngestionReport:
    ingestion_run_id: uuid.UUID | None
    file_name: str
    records_seen: int = 0
    records_imported: int = 0
    duplicates: list[RowNote] = field(default_factory=list)
    errors: list[RowNote] = field(default_factory=list)
    warnings: list[RowNote] = field(default_factory=list)
    posting_ids: list[uuid.UUID] = field(default_factory=list)
    # Filled when the imported postings are processed straight away.
    processed: int = 0
    failed: int = 0
    skills_extracted: int = 0
    roles_matched: int = 0
    review_items: int = 0
    llm_calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ingestion_run_id": str(self.ingestion_run_id) if self.ingestion_run_id else None,
            "file_name": self.file_name,
            "records_seen": self.records_seen,
            "records_imported": self.records_imported,
            "duplicates": len(self.duplicates),
            "errors": len(self.errors),
            "skills_extracted": self.skills_extracted,
            "roles_matched": self.roles_matched,
            "processed": self.processed,
            "failed": self.failed,
            "review_items": self.review_items,
            "llm_calls": self.llm_calls,
            "duplicate_rows": [d.to_dict() for d in self.duplicates],
            "error_rows": [e.to_dict() for e in self.errors],
            "warning_rows": [w.to_dict() for w in self.warnings],
            "posting_ids": [str(p) for p in self.posting_ids],
        }


class IngestionError(Exception):
    """The file as a whole cannot be read (not UTF-8, no header, missing columns ...)."""


def parse_date(text: str) -> date | None:
    text = " ".join(text.split())
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_bool(text: str) -> bool | None:
    value = text.strip().lower()
    return True if value in TRUE else False if value in FALSE else None


def scrub_contacts(text: str | None) -> tuple[str | None, int]:
    """Remove phone numbers and e-mail addresses (job_posting must not store them)."""
    if not text:
        return text, 0
    cleaned, emails = _EMAIL.subn("[contact removed]", text)
    cleaned, phones = _PHONE.subn("[contact removed]", cleaned)
    return cleaned, emails + phones


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.replace(" ", " ").strip()
    return value or None


def read_rows(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestionError(
            f"The file is not UTF-8 text (byte {exc.start}). In Excel use 'Save As -> CSV UTF-8'."
        ) from None
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader, None)
    if not header:
        raise IngestionError("The file is empty (no header row).")
    names = [SYNONYMS.get(h.strip().lower(), h.strip().lower()) for h in header]
    missing = [c for c in REQUIRED if c not in names]
    if missing:
        raise IngestionError(
            f"Missing required column(s): {', '.join(missing)}. Expected: {', '.join(COLUMNS)}"
        )
    rows = []
    for record in reader:
        if not any(cell.strip() for cell in record):
            rows.append({})  # blank line: counted, then skipped
            continue
        rows.append({name: (record[i] if i < len(record) else "") for i, name in enumerate(names)})
        if len(rows) > MAX_ROWS:
            raise IngestionError(f"More than {MAX_ROWS} rows; split the file.")
    return names, rows


def ingest_postings_csv(
    db: Session,
    config: ProductConfig,
    data: bytes,
    *,
    file_name: str,
    default_source: str | None = None,
    today: date | None = None,
) -> IngestionReport:
    """Validate and import the rows (one transaction; the caller commits)."""
    today = today or datetime.now(UTC).date()
    run = IngestionRun(
        source=default_source or "CSV", file_name=file_name, status=RunStatus.RUNNING.value
    )
    db.add(run)
    db.flush()
    report = IngestionReport(run.id, file_name)
    try:
        columns, rows = read_rows(data)
    except IngestionError as exc:
        run.status, run.finished_at = RunStatus.FAILED.value, func.clock_timestamp()
        run.errors_json = [{"row": 0, "reason": str(exc)}]
        db.flush()
        report.errors.append(RowNote(0, None, str(exc)))
        return report
    unknown = [c for c in columns if c not in COLUMNS]
    if unknown:
        report.warnings.append(RowNote(1, None, f"ignored unknown column(s): {', '.join(unknown)}"))

    places = DistrictResolver(db, config)
    cues = load_cues()
    sectors: dict[str, tuple[uuid.UUID, str]] = {}
    for sector_id, code, name in db.execute(select(Sector.id, Sector.code, Sector.name)):
        sectors[normalize_text(code)] = sectors[normalize_text(name)] = (sector_id, code)
    employers: dict[str, list[tuple[uuid.UUID, uuid.UUID]]] = {}
    for employer_id, name, district_id in db.execute(
        select(Employer.id, Employer.name, Employer.district_id)
    ):
        employers.setdefault(normalize_text(name), []).append((employer_id, district_id))

    pending: list[tuple[int, JobPosting, str | None, str | None, str]] = []
    keys_in_file: dict[str, int] = {}
    sources: set[str] = set()
    for number, row in enumerate(rows, start=2):
        report.records_seen += 1
        if not row:
            report.warnings.append(RowNote(number, None, "blank line skipped"))
            continue
        posting, warnings, errors = _build(
            number, row, places, cues, sectors, employers, today, file_name, default_source
        )
        if posting is None:
            report.errors += errors  # a rejected row's warnings would only add noise
            continue
        report.warnings += warnings
        key = posting.dedupe_key
        if key in keys_in_file:
            report.duplicates.append(
                RowNote(number, None, f"duplicate of row {keys_in_file[key]} in this file")
            )
            continue
        keys_in_file[key] = number
        pending.append((number, posting, row.get("district"), row.get("location"), key))
        sources.add(posting.source)

    existing = {}
    keys = [key for *_, key in pending]
    for chunk in (keys[i : i + 1000] for i in range(0, len(keys), 1000)):
        existing.update(
            dict(
                db.execute(
                    select(JobPosting.dedupe_key, JobPosting.id).where(
                        JobPosting.dedupe_key.in_(chunk)
                    )
                ).all()
            )
        )
    for number, posting, district_text, location_text, key in pending:
        if key in existing:
            report.duplicates.append(
                RowNote(
                    number, None, f"duplicate of posting {existing[key]} already in the database"
                )
            )
            continue
        posting.ingestion_run_id = run.id
        db.add(posting)
        db.flush()
        report.posting_ids.append(posting.id)
        if posting.district_id is None:
            db.add(
                ReviewItem(
                    kind=ReviewKind.PLACE_MAPPING.value,
                    payload_json={
                        "district": district_text,
                        "location": location_text,
                        "row": number,
                        "file": file_name,
                    },
                    source_table="job_posting",
                    source_record_id=str(posting.id),
                )
            )
    report.records_imported = len(report.posting_ids)
    run.source = sources.pop() if len(sources) == 1 else (default_source or "MULTIPLE")
    run.rows_loaded = report.records_imported
    run.rows_rejected = len(report.errors) + len(report.duplicates)
    run.errors_json = [
        {"row": n.row, "reason": f"{n.field}: {n.message}" if n.field else n.message}
        for n in [*report.errors, *report.duplicates]
    ]
    run.status = RunStatus.SUCCEEDED.value
    run.finished_at = func.clock_timestamp()
    db.flush()
    return report


def _build(
    number: int,
    row: dict[str, str],
    places: DistrictResolver,
    cues: Any,
    sectors: dict[str, tuple[uuid.UUID, str]],
    employers: dict[str, list[tuple[uuid.UUID, uuid.UUID]]],
    today: date,
    file_name: str,
    default_source: str | None,
) -> tuple[JobPosting | None, list[RowNote], list[RowNote]]:
    """One CSV row -> (an unsaved JobPosting or None, warnings, errors)."""
    warnings: list[RowNote] = []
    errors: list[RowNote] = []

    def error(column: str, message: str) -> None:
        errors.append(RowNote(number, column, message))

    def warn(column: str, message: str) -> None:
        warnings.append(RowNote(number, column, message))

    get = {c: _clean(row.get(c)) for c in COLUMNS}
    title, description = get["title"], get["description"]
    if not title:
        error("title", "missing title")
    if not description:
        warn("description", "no description: skills can only come from the title")
    title, removed_title = scrub_contacts(title)
    description, removed_description = scrub_contacts(description)
    if removed_title + removed_description:
        warn(
            "description",
            f"removed {removed_title + removed_description} phone number(s)/e-mail(s)",
        )

    posted_on = None
    if not get["posted_date"]:
        error("posted_date", "missing date")
    elif (posted_on := parse_date(get["posted_date"])) is None:
        error("posted_date", f"'{get['posted_date']}' is not a date (use YYYY-MM-DD)")
    elif posted_on > today:
        error("posted_date", f"{posted_on} is in the future")
    elif posted_on < EARLIEST_DATE:
        error("posted_date", f"{posted_on} is too old")

    source = get["source"] or default_source
    if not source:
        error(
            "source",
            "missing source ID (provenance is required; see docs/DATA_SOURCE_INVENTORY.md)",
        )
    elif len(source) > 64:
        error("source", "source ID longer than 64 characters")
    flag = get["is_synthetic"]
    is_synthetic = parse_bool(flag) if flag else None
    if flag and is_synthetic is None:
        error("is_synthetic", f"'{flag}' is not true/false")
    looks_synthetic = bool(source) and source.upper().startswith("Y")
    if is_synthetic is None and source and not flag:
        is_synthetic = looks_synthetic
        warn("is_synthetic", f"missing; set to {str(is_synthetic).lower()} from the source ID")
    if is_synthetic is False and looks_synthetic:
        error("is_synthetic", f"source {source} is a synthetic dataset but is_synthetic is false")
    license_note = get["license_note"]
    if not license_note:
        license_note = "TODO-VERIFY"
        warn("license_note", "missing; set to TODO-VERIFY")

    if errors or posted_on is None or not title:
        return None, warnings, errors

    place = places.resolve(get["district"], get["location"])
    if place.district_id is None and (get["district"] or get["location"]):
        warn("district", f"district not recognised ({place.how}); sent to the review queue")
    elif place.district_id is None:
        warn("district", "no district or location given; sent to the review queue")
    sector_id = None
    if get["sector"]:
        found = sectors.get(normalize_text(get["sector"]))
        if found is None:
            warn("sector", f"unknown sector '{get['sector']}'")
        else:
            sector_id = found[0]
    employer_id = None
    if get["employer"]:
        matches = [
            e
            for e, d in employers.get(normalize_text(get["employer"]), [])
            if place.district_id in (None, d)
        ]
        employer_id = matches[0] if len(matches) == 1 else None

    text = f"{title} {description or ''}"
    years = first_years(description or "")
    district_key = place.code or "?" + normalize_text(get["district"] or get["location"] or "")
    posting = JobPosting(
        title=title,
        description=description,
        employer_id=employer_id,
        employer_name_raw=get["employer"],
        district_id=place.district_id,
        sector_id=sector_id,
        location_raw=get["location"] or get["district"],
        posted_on=posted_on,
        quarter=quarter_of(posted_on),
        experience_min_years=Decimal(str(years[0])) if years else None,
        experience_max_years=Decimal(str(years[1])) if years and years[1] is not None else None,
        language=cues.detect_language(text).value,
        dedupe_key=posting_dedupe_key(title, get["employer"], district_key, posted_on),
        extraction_status=ExtractionStatus.PENDING.value,
        source=source,
        source_ref=get["source_ref"] or f"{file_name} row {number}",
        fetched_at=datetime.now(UTC),
        license_note=license_note,
        is_synthetic=bool(is_synthetic),
    )
    return posting, warnings, errors
