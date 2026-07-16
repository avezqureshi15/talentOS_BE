"""add reviews and review_verdict columns to candidates table

Revision ID: 0042
Revises: 0041
Create Date: 2026-07-16

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("reviews", JSONB, nullable=True))
    op.add_column("candidates", sa.Column("review_verdict", sa.String(50), nullable=True))

    op.execute(
        """
        UPDATE candidates
        SET
            reviews = r.reviews,
            review_verdict = r.verdict
        FROM reviews r
        WHERE candidates.current_round_id = r.round_id
          AND r.entity_type = 'ai'
        """
    )


def downgrade() -> None:
    op.drop_column("candidates", "review_verdict")
    op.drop_column("candidates", "reviews")
