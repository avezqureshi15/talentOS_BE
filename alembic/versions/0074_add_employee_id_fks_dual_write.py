"""add employee-FK columns on team/slot/form/round_interviewer tables

Phase 2 of the users↔employees split. Adds a new nullable FK column
pointing at ``employees.id`` alongside the existing user-pointing column
on each affected table, and backfills it via ``users.employee_id`` (the
back-pointer created in 0073). The current column stays untouched so
running code keeps working; a follow-up code PR does dual-write and
switches reads under a feature flag. Phase 3 drops the legacy column
and renames the transitional name to ``employee_id``.

Naming:
  * ``job_team_members`` — new column literally named ``employee_id`` (no
    collision, existing column is ``user_id``).
  * ``slots`` / ``forms`` / ``round_interviewers`` — existing column is
    already ``employee_id`` (misleadingly, points at users). We add
    ``employee_ref_id`` here to avoid same-name-different-meaning
    breakage, and rename it in Phase 3.

Revision ID: 0074
Revises: 0073
Create Date: 2026-08-04

"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0074"
down_revision: str | None = "0073"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


# (table, new_column_name, source_column_name_on_that_table_pointing_at_users)
_TARGETS: tuple[tuple[str, str, str], ...] = (
    ("job_team_members", "employee_id", "user_id"),
    ("slots", "employee_ref_id", "employee_id"),
    ("forms", "employee_ref_id", "employee_id"),
    ("round_interviewers", "employee_ref_id", "employee_id"),
)


def upgrade() -> None:
    for table, new_col, source_col in _TARGETS:
        op.add_column(
            table,
            sa.Column(new_col, sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        )
        op.create_index(f"ix_{table}_{new_col}", table, [new_col])

        op.execute(
            f"""
            UPDATE {table} t
            SET {new_col} = u.employee_id
            FROM users u
            WHERE t.{source_col} = u.id
              AND u.employee_id IS NOT NULL
            """
        )


def downgrade() -> None:
    for table, new_col, _source_col in _TARGETS:
        op.drop_index(f"ix_{table}_{new_col}", table_name=table)
        op.drop_column(table, new_col)
