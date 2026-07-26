"""add round_type column to rounds table

Revision ID: 0051
Revises: 0050
Create Date: 2026-07-26

"""
from alembic import op
import sqlalchemy as sa


revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rounds", sa.Column("round_type", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("rounds", "round_type")
