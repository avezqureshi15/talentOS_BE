"""Add designation column to users table if missing

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("users")]
    if "designation" not in columns:
        op.add_column(
            "users",
            sa.Column("designation", sa.String(length=255), nullable=False, server_default="Unknown"),
        )
        op.alter_column("users", "designation", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "designation")
