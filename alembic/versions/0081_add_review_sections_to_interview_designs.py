"""add review_sections to interview_designs

Revision ID: 0081
Revises: 0080
Create Date: 2026-08-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interview_designs",
        sa.Column(
            "review_sections",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("interview_designs", "review_sections")
