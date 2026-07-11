"""Rename candidates.round_verdict -> final_verdict

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("candidates", "round_verdict", new_column_name="final_verdict")


def downgrade() -> None:
    op.alter_column("candidates", "final_verdict", new_column_name="round_verdict")
