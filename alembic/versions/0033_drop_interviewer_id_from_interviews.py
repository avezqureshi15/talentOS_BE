"""drop interviewer_id from interviews

Revision ID: 0033
Revises: 0032
Create Date: 2026-07-12

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.drop_constraint("interviews_interviewer_id_fkey", "interviews", type_="foreignkey")
    op.drop_column("interviews", "interviewer_id")


def downgrade() -> None:
    op.add_column("interviews", sa.Column("interviewer_id", sa.Integer(), nullable=False))
    op.create_foreign_key("interviews_interviewer_id_fkey", "interviews", "users", ["interviewer_id"], ["id"])
