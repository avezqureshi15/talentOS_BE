"""Add candidate_phone and cover_letter to resume_evaluations

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("resume_evaluations"):
        return
    columns = {col["name"] for col in inspector.get_columns("resume_evaluations")}
    if "candidate_phone" not in columns:
        op.add_column("resume_evaluations", sa.Column("candidate_phone", sa.String(length=30), nullable=True))
    if "cover_letter" not in columns:
        op.add_column("resume_evaluations", sa.Column("cover_letter", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("resume_evaluations", "cover_letter")
    op.drop_column("resume_evaluations", "candidate_phone")
