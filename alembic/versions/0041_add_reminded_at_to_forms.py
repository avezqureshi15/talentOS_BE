"""add reminded_at column to forms table

Revision ID: 0041
Revises: 0040
Create Date: 2026-07-13

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column("forms", sa.Column("reminded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("forms", "reminded_at")
