"""add scheduled_timezone to rounds

Revision ID: 0082
Revises: 0081
Create Date: 2026-08-07

"""
from alembic import op
import sqlalchemy as sa


revision = "0082"
down_revision = "0081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rounds",
        sa.Column("scheduled_timezone", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rounds", "scheduled_timezone")