"""wipe employees table and cascade to every referencing row (dev-only)

Truncates the ``employees`` table and every table that references it,
directly or transitively, so the caller can re-seed from scratch. The
``users`` table (auth) is preserved — its ``employee_id`` back-pointer
is nulled first so it survives the cascade.

Blast radius (Postgres ``TRUNCATE CASCADE`` walks the FK graph):
  employees
    ← slots            (employee_id FK)
        ← interviews   (slot_id FK)
        ← rounds       (slot_id FK)
            ← reviews  (round_id FK)
            ← round_interviewers (round_id FK)
    ← forms            (employee_id FK)
    ← round_interviewers (employee_id FK)
    ← job_team_members (employee_id FK, ON DELETE CASCADE)

DEV ONLY. Do not run on prod without an explicit backup + sign-off.

Revision ID: 0076
Revises: 0075
Create Date: 2026-08-04

"""
from typing import ClassVar

from alembic import op

revision: str = "0076"
down_revision: str | None = "0075"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    # Preserve users (auth). Break the users→employees back-pointer first
    # so employees can be truncated without pulling users into the cascade.
    op.execute("UPDATE users SET employee_id = NULL")

    # One statement: Postgres walks the entire FK dependency graph and
    # truncates every reachable table. ``RESTART IDENTITY`` resets each
    # table's sequence so freshly-seeded rows start at id=1.
    op.execute("TRUNCATE TABLE employees RESTART IDENTITY CASCADE")


def downgrade() -> None:
    # Truncated data is unrecoverable via migration. If you need it back,
    # restore from a backup and mark this revision applied manually.
    raise RuntimeError(
        "0076 is a one-way dev-only cleanup migration; restore from backup"
    )
