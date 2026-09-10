"""add deleted_at to tenants

Distinguishes irreversible tenant delete from suspend (is_active=false).

Revision ID: 0104
Revises: 0103
Create Date: 2026-09-10
"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.engine import Connection

revision: str = "0104"
down_revision: str | None = "0103"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def _column_exists(table: str, column: str) -> bool:
    bind: Connection = op.get_bind()
    return column in {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    if not _column_exists("tenants", "deleted_at"):
        op.add_column(
            "tenants",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("tenants", "deleted_at"):
        op.drop_column("tenants", "deleted_at")
