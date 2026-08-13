"""revoke reviewer evaluate/reject permissions

Bug_030: Reviewer is read-only for candidate status. Remove
application.evaluate and application.reject from the reviewer role.

Revision ID: 0090
Revises: 0089
Create Date: 2026-08-13

"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0090"
down_revision: str | None = "0089"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None

REVIEWER = "reviewer"
REVOKED = ("application.evaluate", "application.reject")


def upgrade() -> None:
    for perm in REVOKED:
        op.execute(
            sa.text(
                "DELETE FROM role_permissions "
                "WHERE role_name = :role AND permission_code = :perm"
            ).bindparams(role=REVIEWER, perm=perm)
        )


def downgrade() -> None:
    for perm in REVOKED:
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (role_name, permission_code) "
                "SELECT :role, :perm WHERE NOT EXISTS ("
                "  SELECT 1 FROM role_permissions "
                "  WHERE role_name = :role AND permission_code = :perm"
                ")"
            ).bindparams(role=REVIEWER, perm=perm)
        )
