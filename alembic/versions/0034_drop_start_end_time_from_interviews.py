"""drop start_time and end_time from interviews

Revision ID: 0034
Revises: 0033
Create Date: 2026-07-12

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.drop_column("interviews", "start_time")
    op.drop_column("interviews", "end_time")


def downgrade() -> None:
    op.add_column("interviews", sa.Column("start_time", sa.DateTime(timezone=True), nullable=False))
    op.add_column("interviews", sa.Column("end_time", sa.DateTime(timezone=True), nullable=False))
