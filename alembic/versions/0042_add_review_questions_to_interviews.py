"""add review questions columns to interviews table

Revision ID: 0042
Revises: 0041
Create Date: 2026-07-22

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column("interviews", sa.Column("transcript_text", sa.Text(), nullable=True))
    op.add_column(
        "interviews",
        sa.Column("review_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("interviews", sa.Column("review_questions_source", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("interviews", "review_questions_source")
    op.drop_column("interviews", "review_questions")
    op.drop_column("interviews", "transcript_text")
