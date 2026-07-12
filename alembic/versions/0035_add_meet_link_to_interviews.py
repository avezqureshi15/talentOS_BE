"""add meet_link column to interviews

Revision ID: 0035
Revises: 0034
Create Date: 2026-07-12

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column("interviews", sa.Column("meet_link", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("interviews", "meet_link")
