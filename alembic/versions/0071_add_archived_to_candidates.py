"""add archived to candidates

Revision ID: 0071
Revises: 0070
Create Date: 2026-08-02

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0071"
down_revision: str | None = "0070"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_candidates_archived", "candidates", ["archived"])


def downgrade() -> None:
    op.drop_index("ix_candidates_archived", table_name="candidates")
    op.drop_column("candidates", "archived")