"""Job intelligence pipeline: evidence on posting links, posting sector and processing status.

- job_posting: sector_id (from the source), processed_at, extraction_error
- posting_skill: evidence_kind, decision, proficiency, evidence_text, evidence_json
- posting_role:  evidence_kind, decision, evidence_text, evidence_json
- extraction methods EXACT, SKILL_PROFILE, ROLE_PROFILE
Existing GENERATED links (synthetic ground truth) become evidence_kind SYNTHETIC.

Written by hand (autogenerate does not detect CHECK constraint changes). The SQL is a
snapshot of the rules at this revision; do not import app code into migrations.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

METHODS_BEFORE = "'ALIAS', 'FUZZY', 'EMBEDDING', 'LLM', 'HUMAN', 'GENERATED'"
METHODS_AFTER = (
    "'EXACT', 'ALIAS', 'FUZZY', 'EMBEDDING', 'LLM', 'HUMAN', 'GENERATED', 'SKILL_PROFILE', "
    "'ROLE_PROFILE'"
)
NEW_METHODS = "'EXACT', 'SKILL_PROFILE', 'ROLE_PROFILE'"
METHOD_CHECKS = [
    ("posting_skill", "method", "ck_posting_skill_method"),
    ("posting_role", "method", "ck_posting_role_method"),
    ("consultation_insight", "extracted_by", "ck_consultation_insight_extracted_by"),
]
EVIDENCE_KINDS = "'OBSERVED', 'INFERRED', 'SYNTHETIC'"
DECISIONS = "'accept', 'review'"
PROFICIENCIES = "'basic', 'intermediate', 'advanced', 'unknown'"


def _evidence_columns(table: str) -> None:
    op.add_column(
        table,
        sa.Column("evidence_kind", sa.String(length=12), server_default="OBSERVED", nullable=False),
    )
    op.add_column(
        table, sa.Column("decision", sa.String(length=8), server_default="accept", nullable=False)
    )
    op.add_column(table, sa.Column("evidence_text", sa.Text(), nullable=True))
    op.add_column(
        table,
        sa.Column(
            "evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f(f"ck_{table}_evidence_kind"), table, f"evidence_kind IN ({EVIDENCE_KINDS})"
    )
    op.create_check_constraint(op.f(f"ck_{table}_decision"), table, f"decision IN ({DECISIONS})")
    op.create_check_constraint(
        op.f(f"ck_{table}_evidence_json_is_object"),
        table,
        "jsonb_typeof(evidence_json) = 'object'",
    )
    # Links written by the synthetic generator are ground truth, not observations.
    op.execute(
        f"UPDATE {table} SET evidence_kind = 'SYNTHETIC' WHERE method = 'GENERATED'"
    )


def upgrade() -> None:
    op.add_column("job_posting", sa.Column("sector_id", sa.Uuid(), nullable=True))
    op.add_column(
        "job_posting", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("job_posting", sa.Column("extraction_error", sa.Text(), nullable=True))
    op.create_index(op.f("ix_job_posting_sector_id"), "job_posting", ["sector_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_job_posting_sector_id_sector"),
        "job_posting",
        "sector",
        ["sector_id"],
        ["id"],
        ondelete="SET NULL",
    )

    _evidence_columns("posting_skill")
    op.add_column(
        "posting_skill",
        sa.Column("proficiency", sa.String(length=16), server_default="unknown", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_posting_skill_proficiency"),
        "posting_skill",
        f"proficiency IN ({PROFICIENCIES})",
    )
    op.execute(
        "UPDATE posting_skill SET evidence_text = matched_text "
        "WHERE method = 'GENERATED' AND evidence_text IS NULL"
    )
    _evidence_columns("posting_role")

    for table, column, name in METHOD_CHECKS:
        op.drop_constraint(op.f(name), table, type_="check")
        op.create_check_constraint(op.f(name), table, f"{column} IN ({METHODS_AFTER})")


def downgrade() -> None:
    # Links made with the new methods cannot exist before this revision; the pipeline can
    # recreate them (python -m app.cli.jobs process).
    op.execute(f"DELETE FROM posting_skill WHERE method IN ({NEW_METHODS})")
    op.execute(f"DELETE FROM posting_role WHERE method IN ({NEW_METHODS})")
    op.execute(f"DELETE FROM consultation_insight WHERE extracted_by IN ({NEW_METHODS})")
    for table, column, name in METHOD_CHECKS:
        op.drop_constraint(op.f(name), table, type_="check")
        op.create_check_constraint(op.f(name), table, f"{column} IN ({METHODS_BEFORE})")

    for table in ("posting_role", "posting_skill"):
        for check in ("evidence_json_is_object", "decision", "evidence_kind"):
            op.drop_constraint(op.f(f"ck_{table}_{check}"), table, type_="check")
        for column in ("evidence_json", "evidence_text", "decision", "evidence_kind"):
            op.drop_column(table, column)
    op.drop_constraint(op.f("ck_posting_skill_proficiency"), "posting_skill", type_="check")
    op.drop_column("posting_skill", "proficiency")

    op.drop_constraint(op.f("fk_job_posting_sector_id_sector"), "job_posting", type_="foreignkey")
    op.drop_index(op.f("ix_job_posting_sector_id"), table_name="job_posting")
    op.drop_column("job_posting", "extraction_error")
    op.drop_column("job_posting", "processed_at")
    op.drop_column("job_posting", "sector_id")
