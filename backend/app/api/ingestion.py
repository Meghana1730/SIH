"""Job-posting ingestion and processing (admin only; docs/06-job-intelligence.md).

POST /ingestion/job-postings                     import a CSV (body text/csv, or JSON
                                                 {"path": "data/raw/job_postings.csv"})
POST /ingestion/job-postings/process-batch       process PENDING postings
POST /ingestion/job-postings/{id}/process        process one posting (?dry_run=true: only show)
GET  /ingestion/job-postings/{id}                a posting with its stored links + evidence
"""

import json
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import DbSession, error, require_roles
from app.config import get_config
from app.core.settings import REPO_ROOT
from app.jobs.ingest import ingest_postings_csv
from app.jobs.processing import (
    GroundTruthConflict,
    JobIntelligence,
    analysis_out,
    posting_out,
    process_batch,
    process_posting,
)
from app.models import AppUser, JobPosting
from app.models.enums import UserRole
from app.schemas.ingestion import BatchOut, IngestionOut, PostingOut, ProcessOut
from app.services.audit import record_audit

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

AdminUser = Annotated[AppUser, Depends(require_roles(UserRole.ADMIN))]
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DATA_DIR = REPO_ROOT / "data"

CSV_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "text/csv": {"schema": {"type": "string"}},
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "example": "data/raw/job_postings.csv",
                            "description": "A CSV file under data/ on the server",
                        }
                    },
                    "required": ["path"],
                }
            },
        },
    }
}


def _read_path(value: Any) -> tuple[bytes, str]:
    if not isinstance(value, str) or not value.strip():
        raise error(400, "BAD_REQUEST", 'Send JSON like {"path": "data/raw/job_postings.csv"}.')
    path = (REPO_ROOT / value).resolve()
    if not path.is_relative_to(DATA_DIR.resolve()) or path.suffix.lower() != ".csv":
        raise error(400, "BAD_PATH", "Only .csv files inside the repository's data/ folder.")
    if not path.is_file():
        raise error(404, "NOT_FOUND", f"No file {value}.")
    return path.read_bytes(), path.relative_to(REPO_ROOT).as_posix()


def _ingest(
    db: Session,
    admin: AppUser,
    data: bytes,
    file_name: str,
    process: bool,
    default_source: str | None,
) -> dict[str, Any]:
    config = get_config()
    report = ingest_postings_csv(
        db, config, data, file_name=file_name, default_source=default_source
    )
    db.commit()
    if process and report.posting_ids:
        batch = process_batch(
            db,
            JobIntelligence.create(db, config),
            limit=len(report.posting_ids),
            posting_ids=report.posting_ids,
        )
        report.processed, report.failed = batch.processed, batch.failed
        report.skills_extracted, report.roles_matched = batch.skills_extracted, batch.roles_matched
        report.review_items, report.llm_calls = batch.review_items, batch.llm_calls
    out = report.to_dict()
    record_audit(
        db,
        "ingestion.job_postings",
        user_id=admin.id,
        entity_type="ingestion_run",
        entity_id=report.ingestion_run_id,
        details={
            k: out[k]
            for k in ("file_name", "records_seen", "records_imported", "duplicates", "errors")
        },
    )
    return out


@router.post("/job-postings", response_model=IngestionOut, openapi_extra=CSV_BODY)
async def ingest_job_postings(
    request: Request,
    admin: AdminUser,
    db: DbSession,
    process: Annotated[bool, Query(description="extract skills and roles right away")] = True,
    file_name: Annotated[str | None, Query(max_length=200)] = None,
    default_source: Annotated[
        str | None, Query(max_length=64, description="source ID for rows without one")
    ] = None,
) -> dict[str, Any]:
    """Import job postings from CSV (columns: title, description, employer, location,
    district, sector, posted_date, source, source_ref, license_note, is_synthetic)."""
    body = await request.body()
    if len(body) > MAX_UPLOAD_BYTES:
        raise error(
            413, "TOO_LARGE", f"The file is larger than {MAX_UPLOAD_BYTES // 1024 // 1024} MB."
        )
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            raise error(400, "BAD_REQUEST", "The body is not valid JSON.") from None
        data, name = _read_path(payload.get("path") if isinstance(payload, dict) else None)
    else:
        data, name = body, file_name or "upload.csv"
    return await run_in_threadpool(
        _ingest, db, admin, data, file_name or name, process, default_source
    )


@router.post("/job-postings/process-batch", response_model=BatchOut)
def process_pending(
    admin: AdminUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    retry_failed: bool = False,
) -> dict[str, Any]:
    """Process PENDING postings (and FAILED ones with retry_failed=true), oldest first."""
    intel = JobIntelligence.create(db, get_config())
    return process_batch(db, intel, limit=limit, retry_failed=retry_failed).to_dict()


def _posting(db: Session, posting_id: uuid.UUID) -> JobPosting:
    posting = db.get(JobPosting, posting_id)
    if posting is None:
        raise error(404, "NOT_FOUND", f"No job posting with id {posting_id}.")
    return posting


@router.post("/job-postings/{posting_id}/process", response_model=ProcessOut)
def process_one(
    posting_id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
    dry_run: Annotated[bool, Query(description="only show the result, store nothing")] = False,
) -> dict[str, Any]:
    posting = _posting(db, posting_id)
    intel = JobIntelligence.create(db, get_config())
    try:
        result = process_posting(db, intel, posting, dry_run=dry_run)
    except GroundTruthConflict as exc:
        raise error(409, "SYNTHETIC_GROUND_TRUTH", str(exc)) from None
    if dry_run:
        db.rollback()  # nothing is stored (not even LLM cache entries)
    else:
        db.commit()
    assert result.analysis is not None
    return {
        "posting_id": str(posting.id),
        "stored": result.stored,
        "extraction_status": posting.extraction_status,
        "review_items_created": result.review_items,
        "is_synthetic": posting.is_synthetic,
        **analysis_out(result.analysis, posting),
    }


@router.get("/job-postings/{posting_id}", response_model=PostingOut)
def get_posting(posting_id: uuid.UUID, admin: AdminUser, db: DbSession) -> dict[str, Any]:
    return posting_out(db, _posting(db, posting_id))
