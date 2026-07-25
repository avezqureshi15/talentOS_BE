"""add candidate_type column to candidates table

Revision ID: 0043
Revises: 0042
Create Date: 2026-07-21

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("candidate_type", sa.String(20), nullable=False, server_default="REGULAR"),
    )


def downgrade() -> None:
    op.drop_column("candidates", "candidate_type")
