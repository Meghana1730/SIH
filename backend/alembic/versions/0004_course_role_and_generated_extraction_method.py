"""Course -> job role link, the GENERATED extraction method, and is_synthetic on links.

- course_role: which job roles a course prepares for (needed to count supply per role).
- ExtractionMethod GENERATED: posting->skill/role links written by the synthetic data
  generator as ground truth (never used for real data).
- is_synthetic on posting_skill, posting_role and consultation_insight: these rows have no
  provenance columns, but a synthetic row must still say so explicitly.

Written by hand (autogenerate does not detect CHECK constraint changes). The SQL below is a
snapshot of the rules at this revision; do not import app code into migrations.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

METHODS_BEFORE = "'ALIAS', 'FUZZY', 'EMBEDDING', 'LLM', 'HUMAN'"
METHODS_AFTER = "'ALIAS', 'FUZZY', 'EMBEDDING', 'LLM', 'HUMAN', 'GENERATED'"
METHOD_CHECKS = [
    ("posting_skill", "method", "ck_posting_skill_method"),
    ("posting_role", "method", "ck_posting_role_method"),
    ("consultation_insight", "extracted_by", "ck_consultation_insight_extracted_by"),
]
LINK_TABLES = ["posting_skill", "posting_role", "consultation_insight"]


def upgrade() -> None:
    op.create_table(
        "course_role",
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
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
            ["course_id"],
            ["course.id"],
            name=op.f("fk_course_role_course_id_course"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_course_role_ingestion_run_id_ingestion_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["job_role.id"],
            name=op.f("fk_course_role_role_id_job_role"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("course_id", "role_id", name=op.f("pk_course_role")),
    )
    op.create_index(
        op.f("ix_course_role_ingestion_run_id"), "course_role", ["ingestion_run_id"], unique=False
    )
    op.create_index(op.f("ix_course_role_role_id"), "course_role", ["role_id"], unique=False)
    op.create_index(
        "uq_course_role_one_primary",
        "course_role",
        ["course_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )

    for table, column, name in METHOD_CHECKS:
        op.drop_constraint(op.f(name), table, type_="check")
        op.create_check_constraint(op.f(name), table, f"{column} IN ({METHODS_AFTER})")

    for table in LINK_TABLES:
        op.add_column(
            table,
            sa.Column(
                "is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False
            ),
        )
    # Links of synthetic parents that already exist are synthetic too.
    op.execute(
        "UPDATE posting_skill SET is_synthetic = true FROM job_posting "
        "WHERE job_posting.id = posting_skill.posting_id AND job_posting.is_synthetic"
    )
    op.execute(
        "UPDATE posting_role SET is_synthetic = true FROM job_posting "
        "WHERE job_posting.id = posting_role.posting_id AND job_posting.is_synthetic"
    )
    op.execute(
        "UPDATE consultation_insight SET is_synthetic = true FROM consultation "
        "WHERE consultation.id = consultation_insight.consultation_id "
        "AND consultation.is_synthetic"
    )


def downgrade() -> None:
    for table in LINK_TABLES:
        op.drop_column(table, "is_synthetic")

    # GENERATED links are synthetic ground truth; they can be regenerated at any time.
    op.execute("DELETE FROM posting_skill WHERE method = 'GENERATED'")
    op.execute("DELETE FROM posting_role WHERE method = 'GENERATED'")
    op.execute("DELETE FROM consultation_insight WHERE extracted_by = 'GENERATED'")
    for table, column, name in METHOD_CHECKS:
        op.drop_constraint(op.f(name), table, type_="check")
        op.create_check_constraint(op.f(name), table, f"{column} IN ({METHODS_BEFORE})")

    op.drop_index(
        "uq_course_role_one_primary",
        table_name="course_role",
        postgresql_where=sa.text("is_primary"),
    )
    op.drop_index(op.f("ix_course_role_role_id"), table_name="course_role")
    op.drop_index(op.f("ix_course_role_ingestion_run_id"), table_name="course_role")
    op.drop_table("course_role")
