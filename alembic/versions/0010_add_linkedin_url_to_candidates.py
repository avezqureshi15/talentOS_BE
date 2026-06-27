"""Add linkedin_url column to candidates

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-26 19:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("linkedin_url", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("candidates", "linkedin_url")
