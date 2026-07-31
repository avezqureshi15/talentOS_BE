"""add rh_external_screening_call_id to candidates

Revision ID: 0057
Revises: 0056
Create Date: 2026-07-30

"""
from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("rh_external_screening_call_id", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("candidates", "rh_external_screening_call_id")
