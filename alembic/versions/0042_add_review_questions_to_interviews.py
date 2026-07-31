"""add review questions columns to interviews table

Revision ID: 0061
Revises: 0059
Create Date: 2026-07-31

No-op migration: this file previously duplicated revision 0042 and its
DDL (interviews.transcript_text / review_questions / review_questions_source)
is already applied to the database. Renumbered to keep the alembic chain
linear; upgrade/downgrade intentionally do nothing.

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0061"
down_revision: str | None = "0059"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
