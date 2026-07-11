"""Change reviews.reviews from Text to JSONB

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("reviews", "reviews", type_=postgresql.JSONB, postgresql_using="reviews::jsonb")


def downgrade() -> None:
    op.alter_column("reviews", "reviews", type_=postgresql.TEXT)
