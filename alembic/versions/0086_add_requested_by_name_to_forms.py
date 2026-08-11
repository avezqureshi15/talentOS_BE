"""add requested_by_name to forms

Revision ID: 0086
Revises: 0085
Create Date: 2026-08-10

"""
from alembic import op
import sqlalchemy as sa


revision = "0086"
down_revision = "0085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "forms",
        sa.Column("requested_by_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("forms", "requested_by_name")
