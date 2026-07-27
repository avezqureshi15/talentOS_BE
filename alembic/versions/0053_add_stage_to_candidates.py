"""add stage column to candidates

Revision ID: 0053
Revises: 0052
Create Date: 2026-07-26

"""
from alembic import op
import sqlalchemy as sa


revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("stage", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("candidates", "stage")
