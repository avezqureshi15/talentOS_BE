"""add indexes on candidates.fit_score and candidates.created_at

Revision ID: 0038
Revises: 0037
Create Date: 2026-07-13

"""

from typing import ClassVar

from alembic import op

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.create_index("ix_candidates_fit_score", "candidates", ["fit_score"])
    op.create_index("ix_candidates_created_at", "candidates", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_candidates_fit_score", table_name="candidates")
    op.drop_index("ix_candidates_created_at", table_name="candidates")
