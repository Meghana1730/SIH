"""Supply status labels UNDER_SUPPLIED / OVER_SUPPLIED (mismatch.status, course_health.flags).

The demand/supply/mismatch engine reports UNDER_SUPPLIED, BALANCED, OVER_SUPPLIED and
INSUFFICIENT_DATA. Existing rows (if any) are renamed.

Written by hand (autogenerate does not detect CHECK constraint changes).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RENAMES = [("UNDERSUPPLIED", "UNDER_SUPPLIED"), ("OVERSUPPLIED", "OVER_SUPPLIED")]


def _rename(pairs: list[tuple[str, str]]) -> None:
    for old, new in pairs:
        op.execute(f"UPDATE mismatch SET status = '{new}' WHERE status = '{old}'")
        op.execute(f"UPDATE course_health SET flags = array_replace(flags, '{old}', '{new}')")


def upgrade() -> None:
    op.drop_constraint(op.f("ck_mismatch_status"), "mismatch", type_="check")
    op.drop_constraint(op.f("ck_course_health_flags_known"), "course_health", type_="check")
    _rename(RENAMES)
    op.create_check_constraint(
        op.f("ck_mismatch_status"),
        "mismatch",
        "status IN ('UNDER_SUPPLIED', 'BALANCED', 'OVER_SUPPLIED', 'INSUFFICIENT_DATA')",
    )
    op.create_check_constraint(
        op.f("ck_course_health_flags_known"),
        "course_health",
        "flags <@ ARRAY['OUTDATED', 'AT_RISK', 'LOW_PLACEMENT', 'OVER_SUPPLIED', "
        "'UNDER_SUPPLIED']::varchar[]",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_mismatch_status"), "mismatch", type_="check")
    op.drop_constraint(op.f("ck_course_health_flags_known"), "course_health", type_="check")
    _rename([(new, old) for old, new in RENAMES])
    op.create_check_constraint(
        op.f("ck_mismatch_status"),
        "mismatch",
        "status IN ('UNDERSUPPLIED', 'BALANCED', 'OVERSUPPLIED', 'INSUFFICIENT_DATA')",
    )
    op.create_check_constraint(
        op.f("ck_course_health_flags_known"),
        "course_health",
        "flags <@ ARRAY['OUTDATED', 'AT_RISK', 'LOW_PLACEMENT', 'OVERSUPPLIED', "
        "'UNDERSUPPLIED']::varchar[]",
    )
