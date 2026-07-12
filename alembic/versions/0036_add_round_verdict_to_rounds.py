"""add round_verdict column to rounds

Revision ID: 0036
Revises: 0035
Create Date: 2026-07-12

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column("rounds", sa.Column("round_verdict", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("rounds", "round_verdict")
