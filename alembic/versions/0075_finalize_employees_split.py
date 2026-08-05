"""finalize the users↔employees split (Phase 3 — terminal cutover)

Drops the legacy user-pointing columns and renames the transitional
``employee_ref_id`` back to ``employee_id`` (which now correctly points
at ``employees.id`` on every table).

After this migration, the ``READ_EMPLOYEES`` flag and every ``if
settings.READ_EMPLOYEES`` branch in the codebase are dead — the code
change shipping alongside this migration removes them.

Rollback path recreates the legacy columns and re-backfills them from
``users.employee_id`` (kept as a nullable back-pointer for helpers and
future auto-linking on invite/signup).

Revision ID: 0075
Revises: 0074
Create Date: 2026-08-04

"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0075"
down_revision: str | None = "0074"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


# Tables where the old ``employee_id`` (users FK) is dropped and the
# transitional ``employee_ref_id`` (employees FK) is renamed to
# ``employee_id``.
_RENAMES: tuple[str, ...] = ("slots", "forms", "round_interviewers")


def upgrade() -> None:
    # ── job_team_members: drop legacy user_id, employee_id already correct ──
    op.drop_constraint("uq_job_team_member", "job_team_members", type_="unique")
    op.drop_column("job_team_members", "user_id")
    op.create_unique_constraint(
        "uq_job_team_member",
        "job_team_members",
        ["hiring_request_id", "employee_id"],
    )

    for table in _RENAMES:
        # Drop the transitional index before renaming so we can rebuild it
        # with the final column name.
        op.drop_index(f"ix_{table}_employee_ref_id", table_name=table)
        # Drop legacy users-FK column (called ``employee_id`` today).
        op.drop_column(table, "employee_id")
        # Rename transitional column to the canonical name.
        op.alter_column(table, "employee_ref_id", new_column_name="employee_id")
        # Re-index under the new name.
        op.create_index(f"ix_{table}_employee_id", table, ["employee_id"])


def downgrade() -> None:
    for table in _RENAMES:
        op.drop_index(f"ix_{table}_employee_id", table_name=table)
        op.alter_column(table, "employee_id", new_column_name="employee_ref_id")
        op.create_index(f"ix_{table}_employee_ref_id", table, ["employee_ref_id"])
        # Recreate the legacy users FK column.
        op.add_column(
            table,
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        )
        # Reverse-backfill from ``users.employee_id`` (still present).
        op.execute(
            f"""
            UPDATE {table} t
            SET employee_id = u.id
            FROM users u
            WHERE u.employee_id = t.employee_ref_id
            """
        )

    op.drop_constraint("uq_job_team_member", "job_team_members", type_="unique")
    op.add_column(
        "job_team_members",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.execute(
        """
        UPDATE job_team_members t
        SET user_id = u.id
        FROM users u
        WHERE u.employee_id = t.employee_id
        """
    )
    op.create_unique_constraint(
        "uq_job_team_member",
        "job_team_members",
        ["hiring_request_id", "user_id"],
    )
