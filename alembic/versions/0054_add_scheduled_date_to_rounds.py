"""add scheduled_date/scheduled_time columns to rounds

Revision ID: 0054
Revises: 0053
Create Date: 2026-07-27

"""
from alembic import op
import sqlalchemy as sa


revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rounds", sa.Column("scheduled_date", sa.Date(), nullable=True))
    op.add_column("rounds", sa.Column("scheduled_time", sa.Time(), nullable=True))
    op.add_column("rounds", sa.Column("scheduled_end_date", sa.Date(), nullable=True))
    op.add_column("rounds", sa.Column("scheduled_end_time", sa.Time(), nullable=True))


def downgrade() -> None:
    op.drop_column("rounds", "scheduled_end_time")
    op.drop_column("rounds", "scheduled_end_date")
    op.drop_column("rounds", "scheduled_time")
    op.drop_column("rounds", "scheduled_date")
