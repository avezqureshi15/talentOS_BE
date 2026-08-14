"""add token_version to users

Forces logout (invalidates all outstanding access + refresh tokens) whenever an
admin changes a user's role: role updates bump ``users.token_version`` and the
JWT payload carries the version at issue time, verified in ``get_current_user``.
Existing rows get 0 so pre-existing tokens remain valid until natural expiry.

Revision ID: 0093
Revises: 0092
Create Date: 2026-08-14
"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.engine import Connection

revision: str = "0093"
down_revision: str | None = "0092"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def _column_exists(table: str, column: str) -> bool:
    bind: Connection = op.get_bind()
    return column in {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    if not _column_exists("users", "token_version"):
        op.add_column(
            "users",
            sa.Column(
                "token_version",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
    else:
        bind: Connection = op.get_bind()
        bind.exec_driver_sql("SELECT 1")


def downgrade() -> None:
    op.drop_column("users", "token_version")
