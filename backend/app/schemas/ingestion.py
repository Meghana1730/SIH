"""Response models for the job-posting ingestion and processing endpoints."""

from typing import Any

from pydantic import BaseModel


class RowNoteOut(BaseModel):
    row: int
    field: str | None
    message: str


class IngestionOut(BaseModel):
    ingestion_run_id: str | None
    file_name: str
    records_seen: int
    records_imported: int
    duplicates: int
    errors: int
    skills_extracted: int
    roles_matched: int
    processed: int
    failed: int
    review_items: int
    llm_calls: int
    duplicate_rows: list[RowNoteOut]
    error_rows: list[RowNoteOut]
    warning_rows: list[RowNoteOut]
    posting_ids: list[str]


class SourceRecordOut(BaseModel):
    table: str
    id: str
    source: str
    source_ref: str | None
    license_note: str | None
    ingestion_run_id: str | None
    is_synthetic: bool


class SkillOut(BaseModel):
    skill_code: str
    skill_name: str
    confidence: float
    method: str
    decision: str
    evidence_kind: str  # OBSERVED | INFERRED | SYNTHETIC
    evidence_text: str | None
    matched_text: str | None
    proficiency: str  # requested in the ad, never certified
    is_synthetic: bool | None
    evidence: dict[str, Any]
    source_record: SourceRecordOut | None


class RoleOut(BaseModel):
    role_code: str
    role_title: str
    confidence: float
    method: str
    decision: str
    evidence_kind: str
    evidence_text: str | None
    is_synthetic: bool | None
    evidence: dict[str, Any]
    source_record: SourceRecordOut | None


class UnknownPhraseOut(BaseModel):
    text: str
    evidence_text: str
    closest: list[dict[str, Any]]


class ProcessOut(BaseModel):
    posting_id: str
    stored: bool
    extraction_status: str
    review_items_created: int
    is_synthetic: bool
    role: RoleOut | None
    skills: list[SkillOut]
    unknown_skill_phrases: list[UnknownPhraseOut]
    llm_calls: list[dict[str, Any]]
    notes: list[str]


class StoredSkillOut(SkillOut):
    band: int | None


class PostingOut(BaseModel):
    id: str
    title: str
    description: str | None
    employer: str | None
    district_code: str | None
    sector_code: str | None
    location: str | None
    posted_on: str
    quarter: str
    language: str
    extraction_status: str
    processed_at: str | None
    extraction_error: str | None
    is_synthetic: bool
    provenance: SourceRecordOut
    roles: list[RoleOut]
    skills: list[StoredSkillOut]


class BatchOut(BaseModel):
    selected: int
    processed: int
    failed: int
    skills_extracted: int
    roles_matched: int
    review_items: int
    llm_calls: int
    remaining: int
    failures: list[dict[str, str]]
