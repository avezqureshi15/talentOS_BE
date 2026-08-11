"""backfill employees for users missing employee_id

Admin create_user historically inserted users without calling
ensure_employee_for_user. This migration creates/links employee rows for
any remaining orphans (Bug_012).

Revision ID: 0083
Revises: 0082
Create Date: 2026-08-11

"""
from typing import ClassVar

from alembic import op

revision: str = "0083"
down_revision: str | None = "0082"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    # Link users to an existing employee with the same email when possible.
    op.execute(
        """
        UPDATE users u
        SET employee_id = e.id
        FROM employees e
        WHERE u.email = e.email
          AND u.employee_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM users u2
              WHERE u2.employee_id = e.id
          )
        """
    )

    # Create employee rows for users that still have no link.
    op.execute(
        """
        INSERT INTO employees (
            tenant_id, emp_id, email, name, status,
            designation, department, created_at
        )
        SELECT
            u.tenant_id,
            u.emp_id,
            u.email,
            u.name,
            u.status,
            'Unassigned',
            'Unassigned',
            u.created_at
        FROM users u
        WHERE u.employee_id IS NULL
          AND u.email IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM employees e WHERE e.email = u.email)
        """
    )

    # Link newly created employees.
    op.execute(
        """
        UPDATE users u
        SET employee_id = e.id
        FROM employees e
        WHERE u.email = e.email
          AND u.employee_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM users u2
              WHERE u2.employee_id = e.id
          )
        """
    )


def downgrade() -> None:
    pass
