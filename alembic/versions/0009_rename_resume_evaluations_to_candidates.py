"""Rename resume_evaluations table to candidates

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-26 17:50:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("resume_evaluations", "candidates")


def downgrade() -> None:
    op.rename_table("candidates", "resume_evaluations")
