"""Add missing interviews columns (transcript_text, review_questions, review_questions_source)

Revision 0061 (filename still says "0042_add_review_questions_to_interviews.py"
from before it was renumbered) was turned into a no-op on the mistaken belief
its DDL duplicated the real revision 0042 (which is actually an unrelated
migration, "add_reviews_and_review_verdict_to_candidates"). It never was a
duplicate, so these columns — present on the Interview model and read by
every applications-list query that joins interviews — were never created.

Guarded with has_column checks: at least one deployed environment already had
these three columns added out-of-band (manual DDL, predating this migration),
so a bare add_column would fail with DuplicateColumn and abort the whole
upgrade chain there — which is exactly what happened in production.

Revision ID: 0098
Revises: 0096
Create Date: 2026-09-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0098"
down_revision: Union[str, None] = "0096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("interviews")}

    if "transcript_text" not in existing:
        op.add_column("interviews", sa.Column("transcript_text", sa.Text(), nullable=True))
    if "review_questions" not in existing:
        op.add_column("interviews", sa.Column("review_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if "review_questions_source" not in existing:
        op.add_column("interviews", sa.Column("review_questions_source", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("interviews", "review_questions_source")
    op.drop_column("interviews", "review_questions")
    op.drop_column("interviews", "transcript_text")
