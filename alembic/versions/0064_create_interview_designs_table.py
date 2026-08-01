"""create interview_designs table

Revision ID: 0064
Revises: 0063
Create Date: 2026-08-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_designs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hiring_request_id", sa.Uuid(), nullable=False),
        sa.Column("screening_sections", postgresql.JSONB(), nullable=False),
        sa.Column("interview_sections", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["hiring_request_id"], ["hiring_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hiring_request_id"),
    )
    op.create_index(
        "ix_interview_designs_hiring_request_id",
        "interview_designs",
        ["hiring_request_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_designs_hiring_request_id", table_name="interview_designs")
    op.drop_table("interview_designs")
