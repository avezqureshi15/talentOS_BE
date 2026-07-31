"""add rh_interview_url and rh_unique_token to rounds

Revision ID: 0059
Revises: 0058
Create Date: 2026-07-31

"""
from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0059"
down_revision: str | None = "0058"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column("rounds", sa.Column("rh_interview_url", sa.String(255), nullable=True))
    op.add_column("rounds", sa.Column("rh_unique_token", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("rounds", "rh_unique_token")
    op.drop_column("rounds", "rh_interview_url")
