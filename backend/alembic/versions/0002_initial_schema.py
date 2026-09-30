"""Initial schema: all 51 KaushalSetu tables.

Generated with `alembic revision --autogenerate` from app/models and reviewed by hand.
Groups: geography, taxonomy (Skill Graph, incl. pgvector embeddings), qualifications,
training supply, employers & industry signals, demand, candidates & outcomes,
intelligence results, validation & plans, system tables.
downgrade() drops every table in reverse dependency order (the pgvector extension
itself is removed by 0001's downgrade).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29 17:24:21.678773
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_run",
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="RUNNING", nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_loaded", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rows_rejected", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "errors_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(errors_json) = 'array'",
            name=op.f("ck_ingestion_run_errors_json_is_array"),
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED')",
            name=op.f("ck_ingestion_run_status"),
        ),
        sa.CheckConstraint(
            "finished_at >= started_at", name=op.f("ck_ingestion_run_finished_after_started")
        ),
        sa.CheckConstraint(
            "rows_loaded >= 0 AND rows_rejected >= 0",
            name=op.f("ck_ingestion_run_counts_not_negative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_run")),
    )
    op.create_index(op.f("ix_ingestion_run_source"), "ingestion_run", ["source"], unique=False)
    op.create_table(
        "llm_cache",
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("task", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("cache_key ~ '^[0-9a-f]{64}$'", name=op.f("ck_llm_cache_cache_key_hex")),
        sa.PrimaryKeyConstraint("cache_key", name=op.f("pk_llm_cache")),
    )
    op.create_index(op.f("ix_llm_cache_task"), "llm_cache", ["task"], unique=False)
    op.create_table(
        "district",
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("state_name", sa.String(length=100), nullable=False),
        sa.Column(
            "aliases", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("official_code", sa.String(length=64), nullable=True),
        sa.Column("official_code_scheme", sa.String(length=32), nullable=True),
        sa.Column(
            "official_code_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "NOT official_code_verified OR (official_code IS NOT NULL AND official_code NOT LIKE 'TODO%%')",
            name=op.f("ck_district_official_code_verified_requires_code"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_district_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_district")),
        sa.UniqueConstraint("code", name=op.f("uq_district_code")),
        sa.UniqueConstraint("state_name", "name", name=op.f("uq_district_state_name_name")),
    )
    op.create_index(
        op.f("ix_district_ingestion_run_id"), "district", ["ingestion_run_id"], unique=False
    )
    op.create_index(
        "uq_district_verified_official_code",
        "district",
        ["official_code_scheme", "official_code"],
        unique=True,
        postgresql_where=sa.text("official_code_verified"),
    )
    op.create_table(
        "equipment",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("indicative_cost_inr", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("cost_is_estimate", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("indicative_cost_inr >= 0", name=op.f("ck_equipment_cost_not_negative")),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_equipment_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_equipment")),
        sa.UniqueConstraint("code", name=op.f("uq_equipment_code")),
    )
    op.create_index(
        op.f("ix_equipment_ingestion_run_id"), "equipment", ["ingestion_run_id"], unique=False
    )
    op.create_table(
        "sector",
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("ssc_name", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_sector_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sector")),
        sa.UniqueConstraint("code", name=op.f("uq_sector_code")),
        sa.UniqueConstraint("name", name=op.f("uq_sector_name")),
    )
    op.create_index(
        op.f("ix_sector_ingestion_run_id"), "sector", ["ingestion_run_id"], unique=False
    )
    op.create_table(
        "skill",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("skill_type", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("embedding_model", sa.String(length=120), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "skill_type IN ('TECHNICAL', 'TOOL', 'SAFETY', 'DOMAIN', 'CORE')",
            name=op.f("ck_skill_skill_type"),
        ),
        sa.CheckConstraint(
            "(embedding IS NULL) = (embedding_model IS NULL)",
            name=op.f("ck_skill_embedding_model_recorded"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_skill_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill")),
        sa.UniqueConstraint("code", name=op.f("uq_skill_code")),
        sa.UniqueConstraint("name", name=op.f("uq_skill_name")),
    )
    op.create_index(
        "ix_skill_embedding_hnsw",
        "skill",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(op.f("ix_skill_ingestion_run_id"), "skill", ["ingestion_run_id"], unique=False)
    op.create_table(
        "candidate",
        sa.Column("pseudonym", sa.String(length=40), nullable=False),
        sa.Column("district_id", sa.Uuid(), nullable=False),
        sa.Column("education_level", sa.String(length=16), nullable=False),
        sa.Column(
            "languages",
            postgresql.ARRAY(sa.String(length=8)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "consent_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "education_level IN ('BELOW_CLASS_10', 'CLASS_10', 'CLASS_12', 'ITI', 'DIPLOMA', 'GRADUATE', 'OTHER')",
            name=op.f("ck_candidate_education_level"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(consent_json) = 'object'",
            name=op.f("ck_candidate_consent_json_is_object"),
        ),
        sa.CheckConstraint("is_synthetic", name=op.f("ck_candidate_synthetic_only")),
        sa.ForeignKeyConstraint(
            ["district_id"], ["district.id"], name=op.f("fk_candidate_district_id_district")
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_candidate_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate")),
        sa.UniqueConstraint("pseudonym", name=op.f("uq_candidate_pseudonym")),
    )
    op.create_index(op.f("ix_candidate_district_id"), "candidate", ["district_id"], unique=False)
    op.create_index(
        op.f("ix_candidate_ingestion_run_id"), "candidate", ["ingestion_run_id"], unique=False
    )
    op.create_table(
        "consultation",
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("held_on", sa.Date(), nullable=False),
        sa.Column("district_id", sa.Uuid(), nullable=True),
        sa.Column("sector_id", sa.Uuid(), nullable=True),
        sa.Column("participant_type", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "consent_to_quote", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "participant_type IN ('EMPLOYER', 'INSTRUCTOR', 'ASSOCIATION', 'OFFICIAL', 'OTHER')",
            name=op.f("ck_consultation_participant_type"),
        ),
        sa.ForeignKeyConstraint(
            ["district_id"],
            ["district.id"],
            name=op.f("fk_consultation_district_id_district"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_consultation_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sector_id"],
            ["sector.id"],
            name=op.f("fk_consultation_sector_id_sector"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consultation")),
    )
    op.create_index(
        op.f("ix_consultation_district_id"), "consultation", ["district_id"], unique=False
    )
    op.create_index(
        op.f("ix_consultation_ingestion_run_id"), "consultation", ["ingestion_run_id"], unique=False
    )
    op.create_index(op.f("ix_consultation_sector_id"), "consultation", ["sector_id"], unique=False)
    op.create_table(
        "employer",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=250), nullable=False),
        sa.Column("sector_id", sa.Uuid(), nullable=True),
        sa.Column("district_id", sa.Uuid(), nullable=False),
        sa.Column("size", sa.String(length=16), server_default="UNKNOWN", nullable=False),
        sa.Column("is_msme_registered", sa.Boolean(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "size IN ('MICRO', 'SMALL', 'MEDIUM', 'LARGE', 'UNKNOWN')",
            name=op.f("ck_employer_size"),
        ),
        sa.ForeignKeyConstraint(
            ["district_id"], ["district.id"], name=op.f("fk_employer_district_id_district")
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_employer_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sector_id"],
            ["sector.id"],
            name=op.f("fk_employer_sector_id_sector"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employer")),
        sa.UniqueConstraint("code", name=op.f("uq_employer_code")),
    )
    op.create_index(op.f("ix_employer_district_id"), "employer", ["district_id"], unique=False)
    op.create_index(
        op.f("ix_employer_ingestion_run_id"), "employer", ["ingestion_run_id"], unique=False
    )
    op.create_index(op.f("ix_employer_sector_id"), "employer", ["sector_id"], unique=False)
    op.create_table(
        "institute",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=250), nullable=False),
        sa.Column("institute_type", sa.String(length=16), nullable=False),
        sa.Column("ownership", sa.String(length=16), nullable=True),
        sa.Column("district_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("official_code", sa.String(length=64), nullable=True),
        sa.Column("official_code_scheme", sa.String(length=32), nullable=True),
        sa.Column(
            "official_code_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "NOT official_code_verified OR (official_code IS NOT NULL AND official_code NOT LIKE 'TODO%%')",
            name=op.f("ck_institute_official_code_verified_requires_code"),
        ),
        sa.CheckConstraint(
            "institute_type IN ('ITI', 'PMKVY_TC', 'POLYTECHNIC', 'OTHER')",
            name=op.f("ck_institute_institute_type"),
        ),
        sa.CheckConstraint(
            "ownership IN ('GOVERNMENT', 'PRIVATE', 'OTHER')", name=op.f("ck_institute_ownership")
        ),
        sa.ForeignKeyConstraint(
            ["district_id"], ["district.id"], name=op.f("fk_institute_district_id_district")
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_institute_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institute")),
        sa.UniqueConstraint("code", name=op.f("uq_institute_code")),
    )
    op.create_index(op.f("ix_institute_district_id"), "institute", ["district_id"], unique=False)
    op.create_index(
        op.f("ix_institute_ingestion_run_id"), "institute", ["ingestion_run_id"], unique=False
    )
    op.create_index(
        "uq_institute_verified_official_code",
        "institute",
        ["official_code_scheme", "official_code"],
        unique=True,
        postgresql_where=sa.text("official_code_verified"),
    )
    op.create_table(
        "job_role",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("sector_id", sa.Uuid(), nullable=False),
        sa.Column("nsqf_level", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column(
            "aliases", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("official_code", sa.String(length=64), nullable=True),
        sa.Column("official_code_scheme", sa.String(length=32), nullable=True),
        sa.Column(
            "official_code_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "NOT official_code_verified OR (official_code IS NOT NULL AND official_code NOT LIKE 'TODO%%')",
            name=op.f("ck_job_role_official_code_verified_requires_code"),
        ),
        sa.CheckConstraint(
            "nsqf_level > 0 AND nsqf_level <= 10", name=op.f("ck_job_role_nsqf_level_range")
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_job_role_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sector_id"], ["sector.id"], name=op.f("fk_job_role_sector_id_sector")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_role")),
        sa.UniqueConstraint("code", name=op.f("uq_job_role_code")),
    )
    op.create_index(
        op.f("ix_job_role_ingestion_run_id"), "job_role", ["ingestion_run_id"], unique=False
    )
    op.create_index(op.f("ix_job_role_sector_id"), "job_role", ["sector_id"], unique=False)
    op.create_index(
        "uq_job_role_verified_official_code",
        "job_role",
        ["official_code_scheme", "official_code"],
        unique=True,
        postgresql_where=sa.text("official_code_verified"),
    )
    op.create_table(
        "sector_event",
        sa.Column("sector_id", sa.Uuid(), nullable=False),
        sa.Column("district_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("expected_jobs", sa.Integer(), nullable=True),
        sa.Column("announced_on", sa.Date(), nullable=False),
        sa.Column("announced_quarter", sa.String(length=7), nullable=False),
        sa.Column("realization_factor", sa.Double(), nullable=True),
        sa.Column("citation_url", sa.Text(), nullable=True),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "announced_quarter ~ '^[0-9]{4}Q[1-4]$'",
            name=op.f("ck_sector_event_announced_quarter_format"),
        ),
        sa.CheckConstraint(
            "event_type IN ('NEW_PLANT', 'EXPANSION', 'CLOSURE', 'POLICY', 'PROJECT', 'OTHER')",
            name=op.f("ck_sector_event_event_type"),
        ),
        sa.CheckConstraint(
            "NOT is_simulated OR is_synthetic", name=op.f("ck_sector_event_simulated_is_synthetic")
        ),
        sa.CheckConstraint(
            "expected_jobs >= 0", name=op.f("ck_sector_event_expected_jobs_not_negative")
        ),
        sa.CheckConstraint(
            "realization_factor >= 0 AND realization_factor <= 1",
            name=op.f("ck_sector_event_realization_factor_range"),
        ),
        sa.ForeignKeyConstraint(
            ["district_id"],
            ["district.id"],
            name=op.f("fk_sector_event_district_id_district"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_sector_event_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sector_id"], ["sector.id"], name=op.f("fk_sector_event_sector_id_sector")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sector_event")),
    )
    op.create_index(
        "ix_sector_event_district_quarter",
        "sector_event",
        ["district_id", "announced_quarter"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sector_event_ingestion_run_id"), "sector_event", ["ingestion_run_id"], unique=False
    )
    op.create_index(op.f("ix_sector_event_sector_id"), "sector_event", ["sector_id"], unique=False)
    op.create_table(
        "sector_indicator",
        sa.Column("sector_id", sa.Uuid(), nullable=True),
        sa.Column("district_id", sa.Uuid(), nullable=True),
        sa.Column("geography_level", sa.String(length=16), nullable=False),
        sa.Column("geography_name", sa.String(length=120), nullable=False),
        sa.Column("indicator", sa.String(length=80), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Double(), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "geography_level <> 'DISTRICT' OR district_id IS NOT NULL",
            name=op.f("ck_sector_indicator_district_level_needs_district"),
        ),
        sa.CheckConstraint(
            "geography_level IN ('GLOBAL', 'NATIONAL', 'STATE', 'DISTRICT', 'RTO')",
            name=op.f("ck_sector_indicator_geography_level"),
        ),
        sa.ForeignKeyConstraint(
            ["district_id"],
            ["district.id"],
            name=op.f("fk_sector_indicator_district_id_district"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_sector_indicator_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sector_id"],
            ["sector.id"],
            name=op.f("fk_sector_indicator_sector_id_sector"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sector_indicator")),
        sa.UniqueConstraint(
            "indicator",
            "geography_level",
            "geography_name",
            "period",
            name="uq_sector_indicator_natural_key",
        ),
    )
    op.create_index(
        op.f("ix_sector_indicator_district_id"), "sector_indicator", ["district_id"], unique=False
    )
    op.create_index(
        op.f("ix_sector_indicator_ingestion_run_id"),
        "sector_indicator",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sector_indicator_sector_id"), "sector_indicator", ["sector_id"], unique=False
    )
    op.create_table(
        "skill_alias",
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("alias_normalized", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=8), server_default="en", nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("embedding_model", sa.String(length=120), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("alias_normalized <> ''", name=op.f("ck_skill_alias_alias_not_empty")),
        sa.CheckConstraint("language IN ('en', 'hi', 'mr')", name=op.f("ck_skill_alias_language")),
        sa.CheckConstraint(
            "(embedding IS NULL) = (embedding_model IS NULL)",
            name=op.f("ck_skill_alias_embedding_model_recorded"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_skill_alias_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_skill_alias_skill_id_skill"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill_alias")),
        sa.UniqueConstraint(
            "language", "alias_normalized", name=op.f("uq_skill_alias_language_alias_normalized")
        ),
    )
    op.create_index(
        op.f("ix_skill_alias_alias_normalized"), "skill_alias", ["alias_normalized"], unique=False
    )
    op.create_index(
        op.f("ix_skill_alias_ingestion_run_id"), "skill_alias", ["ingestion_run_id"], unique=False
    )
    op.create_index(op.f("ix_skill_alias_skill_id"), "skill_alias", ["skill_id"], unique=False)
    op.create_table(
        "skill_equipment",
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_id", sa.Uuid(), nullable=False),
        sa.Column("qty_per_batch", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("qty_per_batch > 0", name=op.f("ck_skill_equipment_qty_positive")),
        sa.ForeignKeyConstraint(
            ["equipment_id"],
            ["equipment.id"],
            name=op.f("fk_skill_equipment_equipment_id_equipment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_skill_equipment_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_skill_equipment_skill_id_skill"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("skill_id", "equipment_id", name=op.f("pk_skill_equipment")),
    )
    op.create_index(
        op.f("ix_skill_equipment_equipment_id"), "skill_equipment", ["equipment_id"], unique=False
    )
    op.create_index(
        op.f("ix_skill_equipment_ingestion_run_id"),
        "skill_equipment",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_table(
        "trend_signal",
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("signal_name", sa.String(length=80), nullable=False),
        sa.Column(
            "geography_level", sa.String(length=16), server_default="NATIONAL", nullable=False
        ),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Double(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "geography_level IN ('GLOBAL', 'NATIONAL', 'STATE', 'DISTRICT', 'RTO')",
            name=op.f("ck_trend_signal_geography_level"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_trend_signal_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_trend_signal_skill_id_skill"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trend_signal")),
        sa.UniqueConstraint(
            "skill_id",
            "signal_name",
            "geography_level",
            "period",
            name=op.f("uq_trend_signal_skill_id_signal_name_geography_level_period"),
        ),
    )
    op.create_index(
        op.f("ix_trend_signal_ingestion_run_id"), "trend_signal", ["ingestion_run_id"], unique=False
    )
    op.create_index(op.f("ix_trend_signal_skill_id"), "trend_signal", ["skill_id"], unique=False)
    op.create_table(
        "app_user",
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("state_name", sa.String(length=100), nullable=True),
        sa.Column("district_id", sa.Uuid(), nullable=True),
        sa.Column("institute_id", sa.Uuid(), nullable=True),
        sa.Column("employer_id", sa.Uuid(), nullable=True),
        sa.Column("language", sa.String(length=8), server_default="en", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(role <> 'state_officer' OR state_name IS NOT NULL) AND (role <> 'district_officer' OR district_id IS NOT NULL) AND (role <> 'institute_admin' OR institute_id IS NOT NULL) AND (role <> 'employer' OR employer_id IS NOT NULL)",
            name=op.f("ck_app_user_role_has_scope"),
        ),
        sa.CheckConstraint("language IN ('en', 'hi', 'mr')", name=op.f("ck_app_user_language")),
        sa.CheckConstraint(
            "role IN ('state_officer', 'district_officer', 'institute_admin', 'ssc_reviewer', 'employer', 'admin')",
            name=op.f("ck_app_user_role"),
        ),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_app_user_email_lowercase")),
        sa.ForeignKeyConstraint(
            ["district_id"], ["district.id"], name=op.f("fk_app_user_district_id_district")
        ),
        sa.ForeignKeyConstraint(
            ["employer_id"], ["employer.id"], name=op.f("fk_app_user_employer_id_employer")
        ),
        sa.ForeignKeyConstraint(
            ["institute_id"], ["institute.id"], name=op.f("fk_app_user_institute_id_institute")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("email", name=op.f("uq_app_user_email")),
    )
    op.create_index(op.f("ix_app_user_district_id"), "app_user", ["district_id"], unique=False)
    op.create_index(op.f("ix_app_user_employer_id"), "app_user", ["employer_id"], unique=False)
    op.create_index(op.f("ix_app_user_institute_id"), "app_user", ["institute_id"], unique=False)
    op.create_table(
        "candidate_skill",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("band", sa.SmallInteger(), nullable=False),
        sa.Column("verified_by", sa.String(length=16), server_default="SELF", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "verified_by IN ('SELF', 'ASSESSMENT', 'CERTIFICATE')",
            name=op.f("ck_candidate_skill_verified_by"),
        ),
        sa.CheckConstraint("band >= 1 AND band <= 4", name=op.f("ck_candidate_skill_band_range")),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            name=op.f("fk_candidate_skill_candidate_id_candidate"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_candidate_skill_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_candidate_skill_skill_id_skill"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("candidate_id", "skill_id", name=op.f("pk_candidate_skill")),
    )
    op.create_index(
        op.f("ix_candidate_skill_ingestion_run_id"),
        "candidate_skill",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_skill_skill_id"), "candidate_skill", ["skill_id"], unique=False
    )
    op.create_table(
        "consultation_insight",
        sa.Column("consultation_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=True),
        sa.Column("insight_type", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("quote_approved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("extracted_by", sa.String(length=16), server_default="HUMAN", nullable=False),
        sa.Column("review_status", sa.String(length=16), server_default="PENDING", nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "extracted_by IN ('ALIAS', 'FUZZY', 'EMBEDDING', 'LLM', 'HUMAN')",
            name=op.f("ck_consultation_insight_extracted_by"),
        ),
        sa.CheckConstraint(
            "insight_type IN ('SKILL_GAP', 'OUTDATED_TOPIC', 'EQUIPMENT_NEED', 'OTHER')",
            name=op.f("ck_consultation_insight_insight_type"),
        ),
        sa.CheckConstraint(
            "review_status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name=op.f("ck_consultation_insight_review_status"),
        ),
        sa.CheckConstraint(
            "NOT quote_approved OR quote IS NOT NULL",
            name=op.f("ck_consultation_insight_approved_quote_present"),
        ),
        sa.ForeignKeyConstraint(
            ["consultation_id"],
            ["consultation.id"],
            name=op.f("fk_consultation_insight_consultation_id_consultation"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_consultation_insight_skill_id_skill"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consultation_insight")),
    )
    op.create_index(
        op.f("ix_consultation_insight_consultation_id"),
        "consultation_insight",
        ["consultation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_consultation_insight_skill_id"), "consultation_insight", ["skill_id"], unique=False
    )
    op.create_table(
        "employer_survey_response",
        sa.Column("employer_id", sa.Uuid(), nullable=True),
        sa.Column("district_id", sa.Uuid(), nullable=False),
        sa.Column("business_type", sa.String(length=60), nullable=True),
        sa.Column("business_size", sa.String(length=16), nullable=True),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("language", sa.String(length=8), server_default="en", nullable=False),
        sa.Column("consent_given", sa.Boolean(), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "roles_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "skills_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("hardest_skills_text", sa.Text(), nullable=True),
        sa.Column("apprenticeship_willingness", sa.String(length=8), nullable=True),
        sa.Column("apprentices_possible", sa.Integer(), nullable=True),
        sa.Column(
            "recontact_consent", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "apprenticeship_willingness IN ('YES', 'MAYBE', 'NO')",
            name=op.f("ck_employer_survey_response_apprenticeship_willingness"),
        ),
        sa.CheckConstraint(
            "business_size IN ('MICRO', 'SMALL', 'MEDIUM', 'LARGE', 'UNKNOWN')",
            name=op.f("ck_employer_survey_response_business_size"),
        ),
        sa.CheckConstraint(
            "channel IN ('WEB', 'TELEGRAM', 'WHATSAPP', 'PHONE')",
            name=op.f("ck_employer_survey_response_channel"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(roles_json) = 'array'",
            name=op.f("ck_employer_survey_response_roles_json_is_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(skills_json) = 'array'",
            name=op.f("ck_employer_survey_response_skills_json_is_array"),
        ),
        sa.CheckConstraint(
            "language IN ('en', 'hi', 'mr')", name=op.f("ck_employer_survey_response_language")
        ),
        sa.CheckConstraint(
            "apprentices_possible >= 0",
            name=op.f("ck_employer_survey_response_apprentices_not_negative"),
        ),
        sa.CheckConstraint(
            "consent_given", name=op.f("ck_employer_survey_response_consent_required")
        ),
        sa.ForeignKeyConstraint(
            ["district_id"],
            ["district.id"],
            name=op.f("fk_employer_survey_response_district_id_district"),
        ),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["employer.id"],
            name=op.f("fk_employer_survey_response_employer_id_employer"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_employer_survey_response_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employer_survey_response")),
    )
    op.create_index(
        op.f("ix_employer_survey_response_district_id"),
        "employer_survey_response",
        ["district_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_employer_survey_response_employer_id"),
        "employer_survey_response",
        ["employer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_employer_survey_response_ingestion_run_id"),
        "employer_survey_response",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_employer_survey_response_submitted_at"),
        "employer_survey_response",
        ["submitted_at"],
        unique=False,
    )
    op.create_table(
        "institute_equipment",
        sa.Column("institute_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("condition", sa.String(length=16), server_default="WORKING", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "condition IN ('WORKING', 'NEEDS_REPAIR', 'NOT_WORKING')",
            name=op.f("ck_institute_equipment_condition"),
        ),
        sa.CheckConstraint(
            "quantity >= 0", name=op.f("ck_institute_equipment_quantity_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["equipment_id"],
            ["equipment.id"],
            name=op.f("fk_institute_equipment_equipment_id_equipment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_institute_equipment_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["institute_id"],
            ["institute.id"],
            name=op.f("fk_institute_equipment_institute_id_institute"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "institute_id", "equipment_id", name=op.f("pk_institute_equipment")
        ),
    )
    op.create_index(
        op.f("ix_institute_equipment_equipment_id"),
        "institute_equipment",
        ["equipment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_institute_equipment_ingestion_run_id"),
        "institute_equipment",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_table(
        "job_posting",
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("employer_id", sa.Uuid(), nullable=True),
        sa.Column("employer_name_raw", sa.Text(), nullable=True),
        sa.Column("district_id", sa.Uuid(), nullable=True),
        sa.Column("location_raw", sa.Text(), nullable=True),
        sa.Column("posted_on", sa.Date(), nullable=False),
        sa.Column("quarter", sa.String(length=7), nullable=False),
        sa.Column("salary_min", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("salary_max", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("salary_period", sa.String(length=8), nullable=True),
        sa.Column("experience_min_years", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("experience_max_years", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("language", sa.String(length=8), server_default="en", nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column(
            "extraction_status", sa.String(length=16), server_default="PENDING", nullable=False
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "extraction_status IN ('PENDING', 'DONE', 'FAILED')",
            name=op.f("ck_job_posting_extraction_status"),
        ),
        sa.CheckConstraint("language IN ('en', 'hi', 'mr')", name=op.f("ck_job_posting_language")),
        sa.CheckConstraint(
            "quarter ~ '^[0-9]{4}Q[1-4]$'", name=op.f("ck_job_posting_quarter_format")
        ),
        sa.CheckConstraint(
            "salary_period IN ('DAY', 'MONTH', 'YEAR')", name=op.f("ck_job_posting_salary_period")
        ),
        sa.CheckConstraint(
            "experience_min_years <= experience_max_years",
            name=op.f("ck_job_posting_experience_min_le_max"),
        ),
        sa.CheckConstraint(
            "experience_min_years >= 0", name=op.f("ck_job_posting_experience_not_negative")
        ),
        sa.CheckConstraint(
            "salary_min <= salary_max", name=op.f("ck_job_posting_salary_min_le_max")
        ),
        sa.CheckConstraint("salary_min >= 0", name=op.f("ck_job_posting_salary_min_not_negative")),
        sa.ForeignKeyConstraint(
            ["district_id"],
            ["district.id"],
            name=op.f("fk_job_posting_district_id_district"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["employer.id"],
            name=op.f("fk_job_posting_employer_id_employer"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_job_posting_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_posting")),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_job_posting_dedupe_key")),
    )
    op.create_index(
        "ix_job_posting_district_quarter", "job_posting", ["district_id", "quarter"], unique=False
    )
    op.create_index(
        op.f("ix_job_posting_employer_id"), "job_posting", ["employer_id"], unique=False
    )
    op.create_index(
        op.f("ix_job_posting_ingestion_run_id"), "job_posting", ["ingestion_run_id"], unique=False
    )
    op.create_index(op.f("ix_job_posting_posted_on"), "job_posting", ["posted_on"], unique=False)
    op.create_table(
        "qualification_pack",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("sector_id", sa.Uuid(), nullable=True),
        sa.Column("job_role_id", sa.Uuid(), nullable=True),
        sa.Column("awarding_body", sa.String(length=200), nullable=True),
        sa.Column("nsqf_level", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("version", sa.String(length=20), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("document_url", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("official_code", sa.String(length=64), nullable=True),
        sa.Column("official_code_scheme", sa.String(length=32), nullable=True),
        sa.Column(
            "official_code_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "NOT official_code_verified OR (official_code IS NOT NULL AND official_code NOT LIKE 'TODO%%')",
            name=op.f("ck_qualification_pack_official_code_verified_requires_code"),
        ),
        sa.CheckConstraint(
            "nsqf_level > 0 AND nsqf_level <= 10",
            name=op.f("ck_qualification_pack_nsqf_level_range"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_qualification_pack_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["job_role_id"],
            ["job_role.id"],
            name=op.f("fk_qualification_pack_job_role_id_job_role"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sector_id"],
            ["sector.id"],
            name=op.f("fk_qualification_pack_sector_id_sector"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_qualification_pack")),
        sa.UniqueConstraint("code", name=op.f("uq_qualification_pack_code")),
    )
    op.create_index(
        op.f("ix_qualification_pack_ingestion_run_id"),
        "qualification_pack",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_qualification_pack_job_role_id"),
        "qualification_pack",
        ["job_role_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_qualification_pack_sector_id"), "qualification_pack", ["sector_id"], unique=False
    )
    op.create_index(
        "uq_qualification_pack_verified_official_code",
        "qualification_pack",
        ["official_code_scheme", "official_code", "version"],
        unique=True,
        postgresql_where=sa.text("official_code_verified"),
    )
    op.create_table(
        "role_edge",
        sa.Column("from_role_id", sa.Uuid(), nullable=False),
        sa.Column("to_role_id", sa.Uuid(), nullable=False),
        sa.Column("edge_type", sa.String(length=16), server_default="PROMOTION", nullable=False),
        sa.Column("typical_training_hours", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "edge_type IN ('PROMOTION', 'LATERAL')", name=op.f("ck_role_edge_edge_type")
        ),
        sa.CheckConstraint("from_role_id <> to_role_id", name=op.f("ck_role_edge_no_self_loop")),
        sa.CheckConstraint(
            "typical_training_hours > 0", name=op.f("ck_role_edge_training_hours_positive")
        ),
        sa.ForeignKeyConstraint(
            ["from_role_id"],
            ["job_role.id"],
            name=op.f("fk_role_edge_from_role_id_job_role"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_role_edge_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["to_role_id"],
            ["job_role.id"],
            name=op.f("fk_role_edge_to_role_id_job_role"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_edge")),
        sa.UniqueConstraint(
            "from_role_id", "to_role_id", name=op.f("uq_role_edge_from_role_id_to_role_id")
        ),
    )
    op.create_index(op.f("ix_role_edge_from_role_id"), "role_edge", ["from_role_id"], unique=False)
    op.create_index(
        op.f("ix_role_edge_ingestion_run_id"), "role_edge", ["ingestion_run_id"], unique=False
    )
    op.create_index(op.f("ix_role_edge_to_role_id"), "role_edge", ["to_role_id"], unique=False)
    op.create_table(
        "role_skill",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("importance", sa.Double(), nullable=False),
        sa.Column("required_band", sa.SmallInteger(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "importance >= 0 AND importance <= 1", name=op.f("ck_role_skill_importance_range")
        ),
        sa.CheckConstraint(
            "required_band >= 1 AND required_band <= 4",
            name=op.f("ck_role_skill_required_band_range"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_role_skill_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["job_role.id"],
            name=op.f("fk_role_skill_role_id_job_role"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_role_skill_skill_id_skill"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "skill_id", name=op.f("pk_role_skill")),
    )
    op.create_index(
        op.f("ix_role_skill_ingestion_run_id"), "role_skill", ["ingestion_run_id"], unique=False
    )
    op.create_index(op.f("ix_role_skill_skill_id"), "role_skill", ["skill_id"], unique=False)
    op.create_table(
        "trainer",
        sa.Column("institute_id", sa.Uuid(), nullable=False),
        sa.Column("pseudonym", sa.String(length=40), nullable=False),
        sa.Column(
            "certifications",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("pseudonym <> ''", name=op.f("ck_trainer_pseudonym_not_empty")),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_trainer_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["institute_id"],
            ["institute.id"],
            name=op.f("fk_trainer_institute_id_institute"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trainer")),
        sa.UniqueConstraint(
            "institute_id", "pseudonym", name=op.f("uq_trainer_institute_id_pseudonym")
        ),
    )
    op.create_index(
        op.f("ix_trainer_ingestion_run_id"), "trainer", ["ingestion_run_id"], unique=False
    )
    op.create_index(op.f("ix_trainer_institute_id"), "trainer", ["institute_id"], unique=False)
    op.create_table(
        "audit_log",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column(
            "diff_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(diff_json) = 'object'", name=op.f("ck_audit_log_diff_json_is_object")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_audit_log_user_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"], unique=False)
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"], unique=False)
    op.create_index(op.f("ix_audit_log_user_id"), "audit_log", ["user_id"], unique=False)
    op.create_table(
        "course",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=250), nullable=False),
        sa.Column("course_type", sa.String(length=16), nullable=False),
        sa.Column("sector_id", sa.Uuid(), nullable=True),
        sa.Column("qualification_pack_id", sa.Uuid(), nullable=True),
        sa.Column("duration_hours", sa.Integer(), nullable=True),
        sa.Column("nsqf_level", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("syllabus_version", sa.String(length=40), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("official_code", sa.String(length=64), nullable=True),
        sa.Column("official_code_scheme", sa.String(length=32), nullable=True),
        sa.Column(
            "official_code_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "NOT official_code_verified OR (official_code IS NOT NULL AND official_code NOT LIKE 'TODO%%')",
            name=op.f("ck_course_official_code_verified_requires_code"),
        ),
        sa.CheckConstraint(
            "course_type IN ('ITI_TRADE', 'SHORT_TERM', 'DIPLOMA', 'ADD_ON', 'OTHER')",
            name=op.f("ck_course_course_type"),
        ),
        sa.CheckConstraint("duration_hours > 0", name=op.f("ck_course_duration_positive")),
        sa.CheckConstraint(
            "nsqf_level > 0 AND nsqf_level <= 10", name=op.f("ck_course_nsqf_level_range")
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_course_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["qualification_pack_id"],
            ["qualification_pack.id"],
            name=op.f("fk_course_qualification_pack_id_qualification_pack"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sector_id"],
            ["sector.id"],
            name=op.f("fk_course_sector_id_sector"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course")),
        sa.UniqueConstraint("code", name=op.f("uq_course_code")),
    )
    op.create_index(
        op.f("ix_course_ingestion_run_id"), "course", ["ingestion_run_id"], unique=False
    )
    op.create_index(
        op.f("ix_course_qualification_pack_id"), "course", ["qualification_pack_id"], unique=False
    )
    op.create_index(op.f("ix_course_sector_id"), "course", ["sector_id"], unique=False)
    op.create_index(
        "uq_course_verified_official_code",
        "course",
        ["official_code_scheme", "official_code"],
        unique=True,
        postgresql_where=sa.text("official_code_verified"),
    )
    op.create_table(
        "nos",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("qualification_pack_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("official_code", sa.String(length=64), nullable=True),
        sa.Column("official_code_scheme", sa.String(length=32), nullable=True),
        sa.Column(
            "official_code_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "NOT official_code_verified OR (official_code IS NOT NULL AND official_code NOT LIKE 'TODO%%')",
            name=op.f("ck_nos_official_code_verified_requires_code"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_nos_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["qualification_pack_id"],
            ["qualification_pack.id"],
            name=op.f("fk_nos_qualification_pack_id_qualification_pack"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_nos")),
        sa.UniqueConstraint("code", name=op.f("uq_nos_code")),
    )
    op.create_index(op.f("ix_nos_ingestion_run_id"), "nos", ["ingestion_run_id"], unique=False)
    op.create_index(
        op.f("ix_nos_qualification_pack_id"), "nos", ["qualification_pack_id"], unique=False
    )
    op.create_index(
        "uq_nos_verified_official_code",
        "nos",
        ["official_code_scheme", "official_code"],
        unique=True,
        postgresql_where=sa.text("official_code_verified"),
    )
    op.create_table(
        "posting_role",
        sa.Column("posting_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("confidence", sa.Double(), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "method IN ('ALIAS', 'FUZZY', 'EMBEDDING', 'LLM', 'HUMAN')",
            name=op.f("ck_posting_role_method"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_posting_role_confidence_range")
        ),
        sa.ForeignKeyConstraint(
            ["posting_id"],
            ["job_posting.id"],
            name=op.f("fk_posting_role_posting_id_job_posting"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["job_role.id"],
            name=op.f("fk_posting_role_role_id_job_role"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("posting_id", "role_id", name=op.f("pk_posting_role")),
    )
    op.create_index(op.f("ix_posting_role_role_id"), "posting_role", ["role_id"], unique=False)
    op.create_table(
        "posting_skill",
        sa.Column("posting_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("confidence", sa.Double(), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("band", sa.SmallInteger(), nullable=True),
        sa.Column("matched_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "method IN ('ALIAS', 'FUZZY', 'EMBEDDING', 'LLM', 'HUMAN')",
            name=op.f("ck_posting_skill_method"),
        ),
        sa.CheckConstraint("band >= 1 AND band <= 4", name=op.f("ck_posting_skill_band_range")),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_posting_skill_confidence_range")
        ),
        sa.ForeignKeyConstraint(
            ["posting_id"],
            ["job_posting.id"],
            name=op.f("fk_posting_skill_posting_id_job_posting"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_posting_skill_skill_id_skill"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("posting_id", "skill_id", name=op.f("pk_posting_skill")),
    )
    op.create_index(op.f("ix_posting_skill_skill_id"), "posting_skill", ["skill_id"], unique=False)
    op.create_table(
        "review_item",
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="OPEN", nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Double(), nullable=True),
        sa.Column("suggested_skill_id", sa.Uuid(), nullable=True),
        sa.Column("source_table", sa.String(length=64), nullable=True),
        sa.Column("source_record_id", sa.String(length=64), nullable=True),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolution_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload_json) = 'object'",
            name=op.f("ck_review_item_payload_json_is_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(resolution_json) = 'object'",
            name=op.f("ck_review_item_resolution_json_is_object"),
        ),
        sa.CheckConstraint(
            "kind IN ('SKILL_MAPPING', 'NEW_SKILL', 'PLACE_MAPPING', 'ROLE_MAPPING', 'SYLLABUS_MAPPING')",
            name=op.f("ck_review_item_kind"),
        ),
        sa.CheckConstraint(
            "status = 'OPEN' OR resolved_at IS NOT NULL",
            name=op.f("ck_review_item_resolved_has_timestamp"),
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'ACCEPTED', 'REJECTED', 'REMAPPED')",
            name=op.f("ck_review_item_status"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_review_item_confidence_range")
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["app_user.id"],
            name=op.f("fk_review_item_reviewer_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["suggested_skill_id"],
            ["skill.id"],
            name=op.f("fk_review_item_suggested_skill_id_skill"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_item")),
    )
    op.create_index("ix_review_item_kind_status", "review_item", ["kind", "status"], unique=False)
    op.create_table(
        "scoring_config_version",
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("config_sha256", sa.String(length=64), nullable=False),
        sa.Column("config_yaml", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("approved_by_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "config_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_scoring_config_version_sha256_hex")
        ),
        sa.CheckConstraint(
            "NOT is_active OR approved_at IS NOT NULL",
            name=op.f("ck_scoring_config_version_active_must_be_approved"),
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_id"],
            ["app_user.id"],
            name=op.f("fk_scoring_config_version_approved_by_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["app_user.id"],
            name=op.f("fk_scoring_config_version_created_by_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scoring_config_version")),
        sa.UniqueConstraint("version", name=op.f("uq_scoring_config_version_version")),
    )
    op.create_index(
        "uq_scoring_config_version_one_active",
        "scoring_config_version",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "trainer_skill",
        sa.Column("trainer_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("band", sa.SmallInteger(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("band >= 1 AND band <= 4", name=op.f("ck_trainer_skill_band_range")),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_trainer_skill_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_trainer_skill_skill_id_skill"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trainer_id"],
            ["trainer.id"],
            name=op.f("fk_trainer_skill_trainer_id_trainer"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("trainer_id", "skill_id", name=op.f("pk_trainer_skill")),
    )
    op.create_index(
        op.f("ix_trainer_skill_ingestion_run_id"),
        "trainer_skill",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(op.f("ix_trainer_skill_skill_id"), "trainer_skill", ["skill_id"], unique=False)
    op.create_table(
        "course_module",
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("hours", sa.Numeric(precision=6, scale=1), nullable=True),
        sa.Column("is_elective", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("hours > 0", name=op.f("ck_course_module_hours_positive")),
        sa.CheckConstraint("sequence >= 1", name=op.f("ck_course_module_sequence_positive")),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["course.id"],
            name=op.f("fk_course_module_course_id_course"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_course_module_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_module")),
        sa.UniqueConstraint(
            "course_id", "sequence", name=op.f("uq_course_module_course_id_sequence")
        ),
    )
    op.create_index(
        op.f("ix_course_module_course_id"), "course_module", ["course_id"], unique=False
    )
    op.create_index(
        op.f("ix_course_module_ingestion_run_id"),
        "course_module",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_table(
        "course_offering",
        sa.Column("institute_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("academic_year", sa.String(length=7), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False),
        sa.Column("seats_filled", sa.Integer(), nullable=True),
        sa.Column("completion_rate", sa.Double(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "academic_year ~ '^[0-9]{4}-[0-9]{2}$'",
            name=op.f("ck_course_offering_academic_year_format"),
        ),
        sa.CheckConstraint(
            "completion_rate >= 0 AND completion_rate <= 1",
            name=op.f("ck_course_offering_completion_rate_range"),
        ),
        sa.CheckConstraint("seats >= 0", name=op.f("ck_course_offering_seats_not_negative")),
        sa.CheckConstraint(
            "seats_filled >= 0 AND seats_filled <= seats",
            name=op.f("ck_course_offering_seats_filled_within_seats"),
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["course.id"], name=op.f("fk_course_offering_course_id_course")
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_course_offering_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["institute_id"],
            ["institute.id"],
            name=op.f("fk_course_offering_institute_id_institute"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_offering")),
        sa.UniqueConstraint(
            "institute_id",
            "course_id",
            "academic_year",
            name=op.f("uq_course_offering_institute_id_course_id_academic_year"),
        ),
    )
    op.create_index(
        op.f("ix_course_offering_course_id"), "course_offering", ["course_id"], unique=False
    )
    op.create_index(
        op.f("ix_course_offering_ingestion_run_id"),
        "course_offering",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_course_offering_institute_id"), "course_offering", ["institute_id"], unique=False
    )
    op.create_table(
        "nos_skill",
        sa.Column("nos_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_nos_skill_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["nos_id"], ["nos.id"], name=op.f("fk_nos_skill_nos_id_nos"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"], ["skill.id"], name=op.f("fk_nos_skill_skill_id_skill"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("nos_id", "skill_id", name=op.f("pk_nos_skill")),
    )
    op.create_index(
        op.f("ix_nos_skill_ingestion_run_id"), "nos_skill", ["ingestion_run_id"], unique=False
    )
    op.create_index(op.f("ix_nos_skill_skill_id"), "nos_skill", ["skill_id"], unique=False)
    op.create_table(
        "pipeline_run",
        sa.Column("status", sa.String(length=16), server_default="QUEUED", nullable=False),
        sa.Column("quarter", sa.String(length=7), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("config_version_id", sa.Uuid(), nullable=False),
        sa.Column("triggered_by_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "step_timings_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "NOT is_current OR status = 'SUCCEEDED'",
            name=op.f("ck_pipeline_run_current_must_succeed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(step_timings_json) = 'object'",
            name=op.f("ck_pipeline_run_step_timings_is_object"),
        ),
        sa.CheckConstraint(
            "quarter ~ '^[0-9]{4}Q[1-4]$'", name=op.f("ck_pipeline_run_quarter_format")
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED')",
            name=op.f("ck_pipeline_run_status"),
        ),
        sa.CheckConstraint(
            "finished_at >= started_at", name=op.f("ck_pipeline_run_finished_after_started")
        ),
        sa.ForeignKeyConstraint(
            ["config_version_id"],
            ["scoring_config_version.id"],
            name=op.f("fk_pipeline_run_config_version_id_scoring_config_version"),
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by_id"],
            ["app_user.id"],
            name=op.f("fk_pipeline_run_triggered_by_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_run")),
    )
    op.create_index(
        op.f("ix_pipeline_run_config_version_id"),
        "pipeline_run",
        ["config_version_id"],
        unique=False,
    )
    op.create_index(
        "uq_pipeline_run_one_current",
        "pipeline_run",
        ["is_current"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_table(
        "course_health",
        sa.Column("course_offering_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Double(), nullable=False),
        sa.Column("coverage", sa.Double(), nullable=False),
        sa.Column(
            "flags",
            postgresql.ARRAY(sa.String(length=32)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("confidence", sa.String(length=8), nullable=False),
        sa.Column("synthetic_share", sa.Double(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "components_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("pipeline_run_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence IN ('HIGH', 'MEDIUM', 'LOW')", name=op.f("ck_course_health_confidence")
        ),
        sa.CheckConstraint(
            "flags <@ ARRAY['OUTDATED', 'AT_RISK', 'LOW_PLACEMENT', 'OVERSUPPLIED', 'UNDERSUPPLIED']::varchar[]",
            name=op.f("ck_course_health_flags_known"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(components_json) = 'array'",
            name=op.f("ck_course_health_components_json_is_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence_json) = 'array'",
            name=op.f("ck_course_health_evidence_json_is_array"),
        ),
        sa.CheckConstraint(
            "coverage >= 0 AND coverage <= 1", name=op.f("ck_course_health_coverage_range")
        ),
        sa.CheckConstraint(
            "score >= 0 AND score <= 100", name=op.f("ck_course_health_score_range")
        ),
        sa.CheckConstraint(
            "synthetic_share >= 0 AND synthetic_share <= 1",
            name=op.f("ck_course_health_synthetic_share_range"),
        ),
        sa.ForeignKeyConstraint(
            ["course_offering_id"],
            ["course_offering.id"],
            name=op.f("fk_course_health_course_offering_id_course_offering"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_course_health_pipeline_run_id_pipeline_run"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_health")),
        sa.UniqueConstraint(
            "pipeline_run_id",
            "course_offering_id",
            name=op.f("uq_course_health_pipeline_run_id_course_offering_id"),
        ),
    )
    op.create_index(
        op.f("ix_course_health_course_offering_id"),
        "course_health",
        ["course_offering_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_course_health_pipeline_run_id"), "course_health", ["pipeline_run_id"], unique=False
    )
    op.create_table(
        "demand_score",
        sa.Column("district_id", sa.Uuid(), nullable=False),
        sa.Column("quarter", sa.String(length=7), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=True),
        sa.Column("skill_id", sa.Uuid(), nullable=True),
        sa.Column("score", sa.Double(), nullable=False),
        sa.Column("estimated_openings", sa.Double(), nullable=True),
        sa.Column("mention_count", sa.Integer(), nullable=True),
        sa.Column("trend_status", sa.String(length=16), nullable=True),
        sa.Column("confidence", sa.String(length=8), nullable=False),
        sa.Column("synthetic_share", sa.Double(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "components_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("pipeline_run_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence IN ('HIGH', 'MEDIUM', 'LOW')", name=op.f("ck_demand_score_confidence")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(components_json) = 'array'",
            name=op.f("ck_demand_score_components_json_is_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence_json) = 'array'",
            name=op.f("ck_demand_score_evidence_json_is_array"),
        ),
        sa.CheckConstraint(
            "quarter ~ '^[0-9]{4}Q[1-4]$'", name=op.f("ck_demand_score_quarter_format")
        ),
        sa.CheckConstraint(
            "trend_status IN ('EMERGING', 'STABLE', 'DECLINING')",
            name=op.f("ck_demand_score_trend_status"),
        ),
        sa.CheckConstraint(
            "estimated_openings >= 0", name=op.f("ck_demand_score_openings_not_negative")
        ),
        sa.CheckConstraint(
            "mention_count >= 0", name=op.f("ck_demand_score_mentions_not_negative")
        ),
        sa.CheckConstraint(
            "num_nonnulls(role_id, skill_id) = 1", name=op.f("ck_demand_score_role_xor_skill")
        ),
        sa.CheckConstraint("score >= 0 AND score <= 100", name=op.f("ck_demand_score_score_range")),
        sa.CheckConstraint(
            "synthetic_share >= 0 AND synthetic_share <= 1",
            name=op.f("ck_demand_score_synthetic_share_range"),
        ),
        sa.CheckConstraint(
            "trend_status IS NULL OR skill_id IS NOT NULL",
            name=op.f("ck_demand_score_trend_for_skills"),
        ),
        sa.ForeignKeyConstraint(
            ["district_id"],
            ["district.id"],
            name=op.f("fk_demand_score_district_id_district"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_demand_score_pipeline_run_id_pipeline_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["job_role.id"],
            name=op.f("fk_demand_score_role_id_job_role"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_demand_score_skill_id_skill"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_demand_score")),
    )
    op.create_index(
        op.f("ix_demand_score_pipeline_run_id"), "demand_score", ["pipeline_run_id"], unique=False
    )
    op.create_index(op.f("ix_demand_score_role_id"), "demand_score", ["role_id"], unique=False)
    op.create_index(
        "ix_demand_score_run_district_quarter",
        "demand_score",
        ["pipeline_run_id", "district_id", "quarter"],
        unique=False,
    )
    op.create_index(op.f("ix_demand_score_skill_id"), "demand_score", ["skill_id"], unique=False)
    op.create_index(
        "uq_demand_score_role_row",
        "demand_score",
        ["pipeline_run_id", "district_id", "quarter", "role_id"],
        unique=True,
        postgresql_where=sa.text("role_id IS NOT NULL"),
    )
    op.create_index(
        "uq_demand_score_skill_row",
        "demand_score",
        ["pipeline_run_id", "district_id", "quarter", "skill_id"],
        unique=True,
        postgresql_where=sa.text("skill_id IS NOT NULL"),
    )
    op.create_table(
        "district_plan",
        sa.Column("district_id", sa.Uuid(), nullable=False),
        sa.Column("quarter", sa.String(length=7), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False),
        sa.Column("pipeline_run_id", sa.Uuid(), nullable=True),
        sa.Column(
            "content_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column(
            "languages",
            postgresql.ARRAY(sa.String(length=8)),
            server_default=sa.text("'{en}'"),
            nullable=False,
        ),
        sa.Column("synthetic_share", sa.Double(), server_default=sa.text("0"), nullable=False),
        sa.Column("generated_by_id", sa.Uuid(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(content_json) = 'object'",
            name=op.f("ck_district_plan_content_json_is_object"),
        ),
        sa.CheckConstraint(
            "languages <@ ARRAY['en', 'hi', 'mr']::varchar[]",
            name=op.f("ck_district_plan_languages_known"),
        ),
        sa.CheckConstraint(
            "quarter ~ '^[0-9]{4}Q[1-4]$'", name=op.f("ck_district_plan_quarter_format")
        ),
        sa.CheckConstraint(
            "status <> 'GENERATED' OR generated_at IS NOT NULL",
            name=op.f("ck_district_plan_generated_has_timestamp"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'GENERATED')", name=op.f("ck_district_plan_status")
        ),
        sa.CheckConstraint(
            "synthetic_share >= 0 AND synthetic_share <= 1",
            name=op.f("ck_district_plan_synthetic_share_range"),
        ),
        sa.ForeignKeyConstraint(
            ["district_id"], ["district.id"], name=op.f("fk_district_plan_district_id_district")
        ),
        sa.ForeignKeyConstraint(
            ["generated_by_id"],
            ["app_user.id"],
            name=op.f("fk_district_plan_generated_by_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_district_plan_pipeline_run_id_pipeline_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_district_plan")),
    )
    op.create_index(
        "ix_district_plan_district_quarter",
        "district_plan",
        ["district_id", "quarter"],
        unique=False,
    )
    op.create_index(
        op.f("ix_district_plan_pipeline_run_id"), "district_plan", ["pipeline_run_id"], unique=False
    )
    op.create_table(
        "enrollment",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("course_offering_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ENROLLED", nullable=False),
        sa.Column("enrolled_on", sa.Date(), nullable=False),
        sa.Column("completed_on", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "status <> 'COMPLETED' OR completed_on IS NOT NULL",
            name=op.f("ck_enrollment_completed_needs_date"),
        ),
        sa.CheckConstraint(
            "status IN ('ENROLLED', 'COMPLETED', 'DROPPED')", name=op.f("ck_enrollment_status")
        ),
        sa.CheckConstraint(
            "completed_on >= enrolled_on", name=op.f("ck_enrollment_completed_after_enrolled")
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            name=op.f("fk_enrollment_candidate_id_candidate"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["course_offering_id"],
            ["course_offering.id"],
            name=op.f("fk_enrollment_course_offering_id_course_offering"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_enrollment_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_enrollment")),
        sa.UniqueConstraint(
            "candidate_id",
            "course_offering_id",
            name=op.f("uq_enrollment_candidate_id_course_offering_id"),
        ),
    )
    op.create_index(
        op.f("ix_enrollment_candidate_id"), "enrollment", ["candidate_id"], unique=False
    )
    op.create_index(
        op.f("ix_enrollment_course_offering_id"), "enrollment", ["course_offering_id"], unique=False
    )
    op.create_index(
        op.f("ix_enrollment_ingestion_run_id"), "enrollment", ["ingestion_run_id"], unique=False
    )
    op.create_table(
        "forecast",
        sa.Column("district_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("target_quarter", sa.String(length=7), nullable=False),
        sa.Column("horizon_quarters", sa.SmallInteger(), nullable=False),
        sa.Column("value", sa.Double(), nullable=False),
        sa.Column("lower_bound", sa.Double(), nullable=False),
        sa.Column("upper_bound", sa.Double(), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column(
            "includes_event_uplift", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("confidence", sa.String(length=8), nullable=False),
        sa.Column("synthetic_share", sa.Double(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "components_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("pipeline_run_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence IN ('HIGH', 'MEDIUM', 'LOW')", name=op.f("ck_forecast_confidence")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(components_json) = 'array'",
            name=op.f("ck_forecast_components_json_is_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence_json) = 'array'", name=op.f("ck_forecast_evidence_json_is_array")
        ),
        sa.CheckConstraint(
            "target_quarter ~ '^[0-9]{4}Q[1-4]$'", name=op.f("ck_forecast_target_quarter_format")
        ),
        sa.CheckConstraint(
            "horizon_quarters >= 1 AND horizon_quarters <= 12",
            name=op.f("ck_forecast_horizon_range"),
        ),
        sa.CheckConstraint(
            "lower_bound <= value AND value <= upper_bound",
            name=op.f("ck_forecast_value_within_bounds"),
        ),
        sa.CheckConstraint("lower_bound >= 0", name=op.f("ck_forecast_lower_not_negative")),
        sa.CheckConstraint(
            "synthetic_share >= 0 AND synthetic_share <= 1",
            name=op.f("ck_forecast_synthetic_share_range"),
        ),
        sa.ForeignKeyConstraint(
            ["district_id"],
            ["district.id"],
            name=op.f("fk_forecast_district_id_district"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_forecast_pipeline_run_id_pipeline_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["job_role.id"],
            name=op.f("fk_forecast_role_id_job_role"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecast")),
        sa.UniqueConstraint(
            "pipeline_run_id",
            "district_id",
            "role_id",
            "target_quarter",
            name=op.f("uq_forecast_pipeline_run_id_district_id_role_id_target_quarter"),
        ),
    )
    op.create_index(
        op.f("ix_forecast_pipeline_run_id"), "forecast", ["pipeline_run_id"], unique=False
    )
    op.create_index(op.f("ix_forecast_role_id"), "forecast", ["role_id"], unique=False)
    op.create_table(
        "mismatch",
        sa.Column("district_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("quarter", sa.String(length=7), nullable=False),
        sa.Column("supply", sa.Double(), nullable=False),
        sa.Column("openings", sa.Double(), nullable=False),
        sa.Column("ratio", sa.Double(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.String(length=8), nullable=False),
        sa.Column("synthetic_share", sa.Double(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "components_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("pipeline_run_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence IN ('HIGH', 'MEDIUM', 'LOW')", name=op.f("ck_mismatch_confidence")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(components_json) = 'array'",
            name=op.f("ck_mismatch_components_json_is_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence_json) = 'array'", name=op.f("ck_mismatch_evidence_json_is_array")
        ),
        sa.CheckConstraint("quarter ~ '^[0-9]{4}Q[1-4]$'", name=op.f("ck_mismatch_quarter_format")),
        sa.CheckConstraint(
            "ratio IS NOT NULL OR status = 'INSUFFICIENT_DATA'",
            name=op.f("ck_mismatch_missing_ratio_is_insufficient"),
        ),
        sa.CheckConstraint(
            "status IN ('UNDERSUPPLIED', 'BALANCED', 'OVERSUPPLIED', 'INSUFFICIENT_DATA')",
            name=op.f("ck_mismatch_status"),
        ),
        sa.CheckConstraint("ratio >= 0", name=op.f("ck_mismatch_ratio_not_negative")),
        sa.CheckConstraint(
            "supply >= 0 AND openings >= 0", name=op.f("ck_mismatch_amounts_not_negative")
        ),
        sa.CheckConstraint(
            "synthetic_share >= 0 AND synthetic_share <= 1",
            name=op.f("ck_mismatch_synthetic_share_range"),
        ),
        sa.ForeignKeyConstraint(
            ["district_id"],
            ["district.id"],
            name=op.f("fk_mismatch_district_id_district"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_mismatch_pipeline_run_id_pipeline_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["job_role.id"],
            name=op.f("fk_mismatch_role_id_job_role"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mismatch")),
        sa.UniqueConstraint(
            "pipeline_run_id",
            "district_id",
            "role_id",
            "quarter",
            name=op.f("uq_mismatch_pipeline_run_id_district_id_role_id_quarter"),
        ),
    )
    op.create_index(
        op.f("ix_mismatch_pipeline_run_id"), "mismatch", ["pipeline_run_id"], unique=False
    )
    op.create_index(op.f("ix_mismatch_role_id"), "mismatch", ["role_id"], unique=False)
    op.create_table(
        "module_skill",
        sa.Column("module_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("band_taught", sa.SmallInteger(), nullable=False),
        sa.Column("review_status", sa.String(length=16), server_default="APPROVED", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "review_status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name=op.f("ck_module_skill_review_status"),
        ),
        sa.CheckConstraint(
            "band_taught >= 1 AND band_taught <= 4", name=op.f("ck_module_skill_band_taught_range")
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_module_skill_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["course_module.id"],
            name=op.f("fk_module_skill_module_id_course_module"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_module_skill_skill_id_skill"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("module_id", "skill_id", name=op.f("pk_module_skill")),
    )
    op.create_index(
        op.f("ix_module_skill_ingestion_run_id"), "module_skill", ["ingestion_run_id"], unique=False
    )
    op.create_index(op.f("ix_module_skill_skill_id"), "module_skill", ["skill_id"], unique=False)
    op.create_table(
        "recommendation",
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("rec_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="DRAFT", nullable=False),
        sa.Column("priority", sa.String(length=8), nullable=False),
        sa.Column("confidence", sa.String(length=8), nullable=False),
        sa.Column("decision_owner", sa.String(length=20), nullable=True),
        sa.Column("district_id", sa.Uuid(), nullable=False),
        sa.Column("institute_id", sa.Uuid(), nullable=True),
        sa.Column("course_offering_id", sa.Uuid(), nullable=True),
        sa.Column("role_id", sa.Uuid(), nullable=True),
        sa.Column("skill_id", sa.Uuid(), nullable=True),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "limited_evidence", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("synthetic_share", sa.Double(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("first_run_id", sa.Uuid(), nullable=True),
        sa.Column("last_seen_run_id", sa.Uuid(), nullable=True),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_changed_by_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "NOT limited_evidence OR confidence = 'LOW'",
            name=op.f("ck_recommendation_limited_evidence_low_confidence"),
        ),
        sa.CheckConstraint(
            "confidence IN ('HIGH', 'MEDIUM', 'LOW')", name=op.f("ck_recommendation_confidence")
        ),
        sa.CheckConstraint(
            "decision_owner IN ('DGT_PROCESS', 'SSC', 'STATE_BOARD', 'INSTITUTE', 'DISTRICT_COMMITTEE')",
            name=op.f("ck_recommendation_decision_owner"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence_json) = 'array'",
            name=op.f("ck_recommendation_evidence_json_is_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload_json) = 'object'",
            name=op.f("ck_recommendation_payload_json_is_object"),
        ),
        sa.CheckConstraint(
            "priority IN ('HIGH', 'MEDIUM', 'LOW')", name=op.f("ck_recommendation_priority")
        ),
        sa.CheckConstraint(
            "rec_type IN ('ADD_MODULE', 'UPDATE_MODULE', 'DEMOTE_MODULE', 'EXPAND_SEATS', 'REDUCE_SEATS', 'NEW_COURSE', 'TRAINER_UPSKILL', 'EQUIPMENT')",
            name=op.f("ck_recommendation_rec_type"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'UNDER_VALIDATION', 'VALIDATED', 'IN_PLAN', 'IMPLEMENTED', 'REJECTED')",
            name=op.f("ck_recommendation_status"),
        ),
        sa.CheckConstraint(
            "limited_evidence OR jsonb_array_length(evidence_json) >= 2",
            name=op.f("ck_recommendation_evidence_required"),
        ),
        sa.CheckConstraint(
            "synthetic_share >= 0 AND synthetic_share <= 1",
            name=op.f("ck_recommendation_synthetic_share_range"),
        ),
        sa.ForeignKeyConstraint(
            ["course_offering_id"],
            ["course_offering.id"],
            name=op.f("fk_recommendation_course_offering_id_course_offering"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["district_id"], ["district.id"], name=op.f("fk_recommendation_district_id_district")
        ),
        sa.ForeignKeyConstraint(
            ["first_run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_recommendation_first_run_id_pipeline_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["institute_id"],
            ["institute.id"],
            name=op.f("fk_recommendation_institute_id_institute"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["last_seen_run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_recommendation_last_seen_run_id_pipeline_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["job_role.id"],
            name=op.f("fk_recommendation_role_id_job_role"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_recommendation_skill_id_skill"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["status_changed_by_id"],
            ["app_user.id"],
            name=op.f("fk_recommendation_status_changed_by_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendation")),
        sa.UniqueConstraint("fingerprint", name=op.f("uq_recommendation_fingerprint")),
    )
    op.create_index(
        op.f("ix_recommendation_course_offering_id"),
        "recommendation",
        ["course_offering_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_district_status",
        "recommendation",
        ["district_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recommendation_institute_id"), "recommendation", ["institute_id"], unique=False
    )
    op.create_index(op.f("ix_recommendation_role_id"), "recommendation", ["role_id"], unique=False)
    op.create_index(
        op.f("ix_recommendation_skill_id"), "recommendation", ["skill_id"], unique=False
    )
    op.create_table(
        "supply_estimate",
        sa.Column("district_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("academic_year", sa.String(length=7), nullable=False),
        sa.Column("trained_output", sa.Double(), nullable=False),
        sa.Column("confidence", sa.String(length=8), nullable=False),
        sa.Column("synthetic_share", sa.Double(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "components_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("pipeline_run_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "academic_year ~ '^[0-9]{4}-[0-9]{2}$'",
            name=op.f("ck_supply_estimate_academic_year_format"),
        ),
        sa.CheckConstraint(
            "confidence IN ('HIGH', 'MEDIUM', 'LOW')", name=op.f("ck_supply_estimate_confidence")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(components_json) = 'array'",
            name=op.f("ck_supply_estimate_components_json_is_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence_json) = 'array'",
            name=op.f("ck_supply_estimate_evidence_json_is_array"),
        ),
        sa.CheckConstraint(
            "synthetic_share >= 0 AND synthetic_share <= 1",
            name=op.f("ck_supply_estimate_synthetic_share_range"),
        ),
        sa.CheckConstraint(
            "trained_output >= 0", name=op.f("ck_supply_estimate_output_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["district_id"],
            ["district.id"],
            name=op.f("fk_supply_estimate_district_id_district"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_supply_estimate_pipeline_run_id_pipeline_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["job_role.id"],
            name=op.f("fk_supply_estimate_role_id_job_role"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supply_estimate")),
        sa.UniqueConstraint(
            "pipeline_run_id",
            "district_id",
            "role_id",
            "academic_year",
            name="uq_supply_estimate_run_district_role_year",
        ),
    )
    op.create_index(
        op.f("ix_supply_estimate_pipeline_run_id"),
        "supply_estimate",
        ["pipeline_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supply_estimate_role_id"), "supply_estimate", ["role_id"], unique=False
    )
    op.create_table(
        "placement_outcome",
        sa.Column("enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("placed", sa.Boolean(), nullable=False),
        sa.Column("placement_type", sa.String(length=16), nullable=True),
        sa.Column("employer_id", sa.Uuid(), nullable=True),
        sa.Column("role_id", sa.Uuid(), nullable=True),
        sa.Column("salary_monthly_inr", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("placed_on", sa.Date(), nullable=True),
        sa.Column("retained_6m", sa.Boolean(), nullable=True),
        sa.Column("related_to_training", sa.Boolean(), nullable=True),
        sa.Column("verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "placement_type IN ('WAGE', 'SELF_EMPLOYED', 'APPRENTICESHIP')",
            name=op.f("ck_placement_outcome_placement_type"),
        ),
        sa.CheckConstraint(
            "placed OR (placement_type IS NULL AND employer_id IS NULL AND salary_monthly_inr IS NULL AND placed_on IS NULL)",
            name=op.f("ck_placement_outcome_not_placed_has_no_details"),
        ),
        sa.CheckConstraint(
            "salary_monthly_inr >= 0", name=op.f("ck_placement_outcome_salary_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["employer.id"],
            name=op.f("fk_placement_outcome_employer_id_employer"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["enrollment.id"],
            name=op.f("fk_placement_outcome_enrollment_id_enrollment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_placement_outcome_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["job_role.id"],
            name=op.f("fk_placement_outcome_role_id_job_role"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_placement_outcome")),
        sa.UniqueConstraint("enrollment_id", name=op.f("uq_placement_outcome_enrollment_id")),
    )
    op.create_index(
        op.f("ix_placement_outcome_employer_id"), "placement_outcome", ["employer_id"], unique=False
    )
    op.create_index(
        op.f("ix_placement_outcome_ingestion_run_id"),
        "placement_outcome",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_placement_outcome_role_id"), "placement_outcome", ["role_id"], unique=False
    )
    op.create_table(
        "pledge",
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("employer_id", sa.Uuid(), nullable=False),
        sa.Column("pledge_type", sa.String(length=16), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("timeframe_months", sa.SmallInteger(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "pledge_type IN ('APPRENTICE', 'HIRE')", name=op.f("ck_pledge_pledge_type")
        ),
        sa.CheckConstraint("count >= 1 AND count <= 10000", name=op.f("ck_pledge_count_range")),
        sa.CheckConstraint(
            "timeframe_months >= 1 AND timeframe_months <= 36",
            name=op.f("ck_pledge_timeframe_range"),
        ),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["employer.id"],
            name=op.f("fk_pledge_employer_id_employer"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["recommendation.id"],
            name=op.f("fk_pledge_recommendation_id_recommendation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pledge")),
        sa.UniqueConstraint(
            "recommendation_id",
            "employer_id",
            "pledge_type",
            name=op.f("uq_pledge_recommendation_id_employer_id_pledge_type"),
        ),
    )
    op.create_index(op.f("ix_pledge_employer_id"), "pledge", ["employer_id"], unique=False)
    op.create_index(
        op.f("ix_pledge_recommendation_id"), "pledge", ["recommendation_id"], unique=False
    )
    op.create_table(
        "validation_vote",
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("employer_id", sa.Uuid(), nullable=False),
        sa.Column("vote", sa.String(length=16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "vote IN ('APPROVE', 'REJECT', 'NOT_NEEDED')", name=op.f("ck_validation_vote_vote")
        ),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["employer.id"],
            name=op.f("fk_validation_vote_employer_id_employer"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["recommendation.id"],
            name=op.f("fk_validation_vote_recommendation_id_recommendation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_validation_vote")),
        sa.UniqueConstraint(
            "recommendation_id",
            "employer_id",
            name=op.f("uq_validation_vote_recommendation_id_employer_id"),
        ),
    )
    op.create_index(
        op.f("ix_validation_vote_employer_id"), "validation_vote", ["employer_id"], unique=False
    )
    op.create_index(
        op.f("ix_validation_vote_recommendation_id"),
        "validation_vote",
        ["recommendation_id"],
        unique=False,
    )
    op.create_table(
        "employer_rating",
        sa.Column("placement_outcome_id", sa.Uuid(), nullable=False),
        sa.Column("employer_id", sa.Uuid(), nullable=True),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column(
            "skill_feedback",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("rated_on", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "jsonb_typeof(skill_feedback) = 'object'",
            name=op.f("ck_employer_rating_skill_feedback_is_object"),
        ),
        sa.CheckConstraint(
            "rating >= 1 AND rating <= 5", name=op.f("ck_employer_rating_rating_range")
        ),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["employer.id"],
            name=op.f("fk_employer_rating_employer_id_employer"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_employer_rating_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["placement_outcome_id"],
            ["placement_outcome.id"],
            name=op.f("fk_employer_rating_placement_outcome_id_placement_outcome"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employer_rating")),
        sa.UniqueConstraint(
            "placement_outcome_id", name=op.f("uq_employer_rating_placement_outcome_id")
        ),
    )
    op.create_index(
        op.f("ix_employer_rating_employer_id"), "employer_rating", ["employer_id"], unique=False
    )
    op.create_index(
        op.f("ix_employer_rating_ingestion_run_id"),
        "employer_rating",
        ["ingestion_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_employer_rating_ingestion_run_id"), table_name="employer_rating")
    op.drop_index(op.f("ix_employer_rating_employer_id"), table_name="employer_rating")
    op.drop_table("employer_rating")
    op.drop_index(op.f("ix_validation_vote_recommendation_id"), table_name="validation_vote")
    op.drop_index(op.f("ix_validation_vote_employer_id"), table_name="validation_vote")
    op.drop_table("validation_vote")
    op.drop_index(op.f("ix_pledge_recommendation_id"), table_name="pledge")
    op.drop_index(op.f("ix_pledge_employer_id"), table_name="pledge")
    op.drop_table("pledge")
    op.drop_index(op.f("ix_placement_outcome_role_id"), table_name="placement_outcome")
    op.drop_index(op.f("ix_placement_outcome_ingestion_run_id"), table_name="placement_outcome")
    op.drop_index(op.f("ix_placement_outcome_employer_id"), table_name="placement_outcome")
    op.drop_table("placement_outcome")
    op.drop_index(op.f("ix_supply_estimate_role_id"), table_name="supply_estimate")
    op.drop_index(op.f("ix_supply_estimate_pipeline_run_id"), table_name="supply_estimate")
    op.drop_table("supply_estimate")
    op.drop_index(op.f("ix_recommendation_skill_id"), table_name="recommendation")
    op.drop_index(op.f("ix_recommendation_role_id"), table_name="recommendation")
    op.drop_index(op.f("ix_recommendation_institute_id"), table_name="recommendation")
    op.drop_index("ix_recommendation_district_status", table_name="recommendation")
    op.drop_index(op.f("ix_recommendation_course_offering_id"), table_name="recommendation")
    op.drop_table("recommendation")
    op.drop_index(op.f("ix_module_skill_skill_id"), table_name="module_skill")
    op.drop_index(op.f("ix_module_skill_ingestion_run_id"), table_name="module_skill")
    op.drop_table("module_skill")
    op.drop_index(op.f("ix_mismatch_role_id"), table_name="mismatch")
    op.drop_index(op.f("ix_mismatch_pipeline_run_id"), table_name="mismatch")
    op.drop_table("mismatch")
    op.drop_index(op.f("ix_forecast_role_id"), table_name="forecast")
    op.drop_index(op.f("ix_forecast_pipeline_run_id"), table_name="forecast")
    op.drop_table("forecast")
    op.drop_index(op.f("ix_enrollment_ingestion_run_id"), table_name="enrollment")
    op.drop_index(op.f("ix_enrollment_course_offering_id"), table_name="enrollment")
    op.drop_index(op.f("ix_enrollment_candidate_id"), table_name="enrollment")
    op.drop_table("enrollment")
    op.drop_index(op.f("ix_district_plan_pipeline_run_id"), table_name="district_plan")
    op.drop_index("ix_district_plan_district_quarter", table_name="district_plan")
    op.drop_table("district_plan")
    op.drop_index(
        "uq_demand_score_skill_row",
        table_name="demand_score",
        postgresql_where=sa.text("skill_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_demand_score_role_row",
        table_name="demand_score",
        postgresql_where=sa.text("role_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_demand_score_skill_id"), table_name="demand_score")
    op.drop_index("ix_demand_score_run_district_quarter", table_name="demand_score")
    op.drop_index(op.f("ix_demand_score_role_id"), table_name="demand_score")
    op.drop_index(op.f("ix_demand_score_pipeline_run_id"), table_name="demand_score")
    op.drop_table("demand_score")
    op.drop_index(op.f("ix_course_health_pipeline_run_id"), table_name="course_health")
    op.drop_index(op.f("ix_course_health_course_offering_id"), table_name="course_health")
    op.drop_table("course_health")
    op.drop_index(
        "uq_pipeline_run_one_current",
        table_name="pipeline_run",
        postgresql_where=sa.text("is_current"),
    )
    op.drop_index(op.f("ix_pipeline_run_config_version_id"), table_name="pipeline_run")
    op.drop_table("pipeline_run")
    op.drop_index(op.f("ix_nos_skill_skill_id"), table_name="nos_skill")
    op.drop_index(op.f("ix_nos_skill_ingestion_run_id"), table_name="nos_skill")
    op.drop_table("nos_skill")
    op.drop_index(op.f("ix_course_offering_institute_id"), table_name="course_offering")
    op.drop_index(op.f("ix_course_offering_ingestion_run_id"), table_name="course_offering")
    op.drop_index(op.f("ix_course_offering_course_id"), table_name="course_offering")
    op.drop_table("course_offering")
    op.drop_index(op.f("ix_course_module_ingestion_run_id"), table_name="course_module")
    op.drop_index(op.f("ix_course_module_course_id"), table_name="course_module")
    op.drop_table("course_module")
    op.drop_index(op.f("ix_trainer_skill_skill_id"), table_name="trainer_skill")
    op.drop_index(op.f("ix_trainer_skill_ingestion_run_id"), table_name="trainer_skill")
    op.drop_table("trainer_skill")
    op.drop_index(
        "uq_scoring_config_version_one_active",
        table_name="scoring_config_version",
        postgresql_where=sa.text("is_active"),
    )
    op.drop_table("scoring_config_version")
    op.drop_index("ix_review_item_kind_status", table_name="review_item")
    op.drop_table("review_item")
    op.drop_index(op.f("ix_posting_skill_skill_id"), table_name="posting_skill")
    op.drop_table("posting_skill")
    op.drop_index(op.f("ix_posting_role_role_id"), table_name="posting_role")
    op.drop_table("posting_role")
    op.drop_index(
        "uq_nos_verified_official_code",
        table_name="nos",
        postgresql_where=sa.text("official_code_verified"),
    )
    op.drop_index(op.f("ix_nos_qualification_pack_id"), table_name="nos")
    op.drop_index(op.f("ix_nos_ingestion_run_id"), table_name="nos")
    op.drop_table("nos")
    op.drop_index(
        "uq_course_verified_official_code",
        table_name="course",
        postgresql_where=sa.text("official_code_verified"),
    )
    op.drop_index(op.f("ix_course_sector_id"), table_name="course")
    op.drop_index(op.f("ix_course_qualification_pack_id"), table_name="course")
    op.drop_index(op.f("ix_course_ingestion_run_id"), table_name="course")
    op.drop_table("course")
    op.drop_index(op.f("ix_audit_log_user_id"), table_name="audit_log")
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index(op.f("ix_trainer_institute_id"), table_name="trainer")
    op.drop_index(op.f("ix_trainer_ingestion_run_id"), table_name="trainer")
    op.drop_table("trainer")
    op.drop_index(op.f("ix_role_skill_skill_id"), table_name="role_skill")
    op.drop_index(op.f("ix_role_skill_ingestion_run_id"), table_name="role_skill")
    op.drop_table("role_skill")
    op.drop_index(op.f("ix_role_edge_to_role_id"), table_name="role_edge")
    op.drop_index(op.f("ix_role_edge_ingestion_run_id"), table_name="role_edge")
    op.drop_index(op.f("ix_role_edge_from_role_id"), table_name="role_edge")
    op.drop_table("role_edge")
    op.drop_index(
        "uq_qualification_pack_verified_official_code",
        table_name="qualification_pack",
        postgresql_where=sa.text("official_code_verified"),
    )
    op.drop_index(op.f("ix_qualification_pack_sector_id"), table_name="qualification_pack")
    op.drop_index(op.f("ix_qualification_pack_job_role_id"), table_name="qualification_pack")
    op.drop_index(op.f("ix_qualification_pack_ingestion_run_id"), table_name="qualification_pack")
    op.drop_table("qualification_pack")
    op.drop_index(op.f("ix_job_posting_posted_on"), table_name="job_posting")
    op.drop_index(op.f("ix_job_posting_ingestion_run_id"), table_name="job_posting")
    op.drop_index(op.f("ix_job_posting_employer_id"), table_name="job_posting")
    op.drop_index("ix_job_posting_district_quarter", table_name="job_posting")
    op.drop_table("job_posting")
    op.drop_index(op.f("ix_institute_equipment_ingestion_run_id"), table_name="institute_equipment")
    op.drop_index(op.f("ix_institute_equipment_equipment_id"), table_name="institute_equipment")
    op.drop_table("institute_equipment")
    op.drop_index(
        op.f("ix_employer_survey_response_submitted_at"), table_name="employer_survey_response"
    )
    op.drop_index(
        op.f("ix_employer_survey_response_ingestion_run_id"), table_name="employer_survey_response"
    )
    op.drop_index(
        op.f("ix_employer_survey_response_employer_id"), table_name="employer_survey_response"
    )
    op.drop_index(
        op.f("ix_employer_survey_response_district_id"), table_name="employer_survey_response"
    )
    op.drop_table("employer_survey_response")
    op.drop_index(op.f("ix_consultation_insight_skill_id"), table_name="consultation_insight")
    op.drop_index(
        op.f("ix_consultation_insight_consultation_id"), table_name="consultation_insight"
    )
    op.drop_table("consultation_insight")
    op.drop_index(op.f("ix_candidate_skill_skill_id"), table_name="candidate_skill")
    op.drop_index(op.f("ix_candidate_skill_ingestion_run_id"), table_name="candidate_skill")
    op.drop_table("candidate_skill")
    op.drop_index(op.f("ix_app_user_institute_id"), table_name="app_user")
    op.drop_index(op.f("ix_app_user_employer_id"), table_name="app_user")
    op.drop_index(op.f("ix_app_user_district_id"), table_name="app_user")
    op.drop_table("app_user")
    op.drop_index(op.f("ix_trend_signal_skill_id"), table_name="trend_signal")
    op.drop_index(op.f("ix_trend_signal_ingestion_run_id"), table_name="trend_signal")
    op.drop_table("trend_signal")
    op.drop_index(op.f("ix_skill_equipment_ingestion_run_id"), table_name="skill_equipment")
    op.drop_index(op.f("ix_skill_equipment_equipment_id"), table_name="skill_equipment")
    op.drop_table("skill_equipment")
    op.drop_index(op.f("ix_skill_alias_skill_id"), table_name="skill_alias")
    op.drop_index(op.f("ix_skill_alias_ingestion_run_id"), table_name="skill_alias")
    op.drop_index(op.f("ix_skill_alias_alias_normalized"), table_name="skill_alias")
    op.drop_table("skill_alias")
    op.drop_index(op.f("ix_sector_indicator_sector_id"), table_name="sector_indicator")
    op.drop_index(op.f("ix_sector_indicator_ingestion_run_id"), table_name="sector_indicator")
    op.drop_index(op.f("ix_sector_indicator_district_id"), table_name="sector_indicator")
    op.drop_table("sector_indicator")
    op.drop_index(op.f("ix_sector_event_sector_id"), table_name="sector_event")
    op.drop_index(op.f("ix_sector_event_ingestion_run_id"), table_name="sector_event")
    op.drop_index("ix_sector_event_district_quarter", table_name="sector_event")
    op.drop_table("sector_event")
    op.drop_index(
        "uq_job_role_verified_official_code",
        table_name="job_role",
        postgresql_where=sa.text("official_code_verified"),
    )
    op.drop_index(op.f("ix_job_role_sector_id"), table_name="job_role")
    op.drop_index(op.f("ix_job_role_ingestion_run_id"), table_name="job_role")
    op.drop_table("job_role")
    op.drop_index(
        "uq_institute_verified_official_code",
        table_name="institute",
        postgresql_where=sa.text("official_code_verified"),
    )
    op.drop_index(op.f("ix_institute_ingestion_run_id"), table_name="institute")
    op.drop_index(op.f("ix_institute_district_id"), table_name="institute")
    op.drop_table("institute")
    op.drop_index(op.f("ix_employer_sector_id"), table_name="employer")
    op.drop_index(op.f("ix_employer_ingestion_run_id"), table_name="employer")
    op.drop_index(op.f("ix_employer_district_id"), table_name="employer")
    op.drop_table("employer")
    op.drop_index(op.f("ix_consultation_sector_id"), table_name="consultation")
    op.drop_index(op.f("ix_consultation_ingestion_run_id"), table_name="consultation")
    op.drop_index(op.f("ix_consultation_district_id"), table_name="consultation")
    op.drop_table("consultation")
    op.drop_index(op.f("ix_candidate_ingestion_run_id"), table_name="candidate")
    op.drop_index(op.f("ix_candidate_district_id"), table_name="candidate")
    op.drop_table("candidate")
    op.drop_index(op.f("ix_skill_ingestion_run_id"), table_name="skill")
    op.drop_index(
        "ix_skill_embedding_hnsw",
        table_name="skill",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_table("skill")
    op.drop_index(op.f("ix_sector_ingestion_run_id"), table_name="sector")
    op.drop_table("sector")
    op.drop_index(op.f("ix_equipment_ingestion_run_id"), table_name="equipment")
    op.drop_table("equipment")
    op.drop_index(
        "uq_district_verified_official_code",
        table_name="district",
        postgresql_where=sa.text("official_code_verified"),
    )
    op.drop_index(op.f("ix_district_ingestion_run_id"), table_name="district")
    op.drop_table("district")
    op.drop_index(op.f("ix_llm_cache_task"), table_name="llm_cache")
    op.drop_table("llm_cache")
    op.drop_index(op.f("ix_ingestion_run_source"), table_name="ingestion_run")
    op.drop_table("ingestion_run")
