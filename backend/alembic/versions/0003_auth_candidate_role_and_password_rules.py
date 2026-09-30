"""Auth: candidate role, candidate link, scope and password-hash rules on app_user.

- role may now also be 'candidate'; a candidate login can link to one candidate profile.
- scope_matches_role: a user carries only the scope field of its own role.
- password_is_argon2_hash: the database refuses anything that is not an argon2id hash.

Written by hand (autogenerate does not detect CHECK constraint changes). The SQL below is a
snapshot of the rules at this revision; do not import app code into migrations.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES_BEFORE = (
    "'state_officer', 'district_officer', 'institute_admin', 'ssc_reviewer', 'employer', 'admin'"
)
ROLES_AFTER = (
    "'state_officer', 'district_officer', 'institute_admin', 'ssc_reviewer', 'employer', "
    "'candidate', 'admin'"
)


def upgrade() -> None:
    op.add_column("app_user", sa.Column("candidate_id", sa.Uuid(), nullable=True))
    op.create_unique_constraint(op.f("uq_app_user_candidate_id"), "app_user", ["candidate_id"])
    op.create_foreign_key(
        op.f("fk_app_user_candidate_id_candidate"),
        "app_user",
        "candidate",
        ["candidate_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(op.f("ck_app_user_role"), "app_user", type_="check")
    op.create_check_constraint(op.f("ck_app_user_role"), "app_user", f"role IN ({ROLES_AFTER})")
    op.create_check_constraint(
        op.f("ck_app_user_scope_matches_role"),
        "app_user",
        "(state_name IS NULL OR role = 'state_officer') AND "
        "(district_id IS NULL OR role = 'district_officer') AND "
        "(institute_id IS NULL OR role = 'institute_admin') AND "
        "(employer_id IS NULL OR role = 'employer') AND "
        "(candidate_id IS NULL OR role = 'candidate')",
    )
    op.create_check_constraint(
        op.f("ck_app_user_password_is_argon2_hash"),
        "app_user",
        "password_hash LIKE '$argon2id$%'",
    )


def downgrade() -> None:
    # Refuse (instead of silently deleting accounts) if candidate users exist.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM app_user WHERE role = 'candidate') THEN
                RAISE EXCEPTION 'Cannot downgrade: candidate accounts exist in app_user. '
                    'Delete or convert them first.';
            END IF;
        END $$;
        """)
    op.drop_constraint(op.f("ck_app_user_password_is_argon2_hash"), "app_user", type_="check")
    op.drop_constraint(op.f("ck_app_user_scope_matches_role"), "app_user", type_="check")
    op.drop_constraint(op.f("ck_app_user_role"), "app_user", type_="check")
    op.create_check_constraint(op.f("ck_app_user_role"), "app_user", f"role IN ({ROLES_BEFORE})")
    op.drop_constraint(op.f("fk_app_user_candidate_id_candidate"), "app_user", type_="foreignkey")
    op.drop_constraint(op.f("uq_app_user_candidate_id"), "app_user", type_="unique")
    op.drop_column("app_user", "candidate_id")
