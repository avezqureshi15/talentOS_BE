"""Merge 0013 and 0018 heads

Revision ID: 0019
Revises: 0013, 0018
Create Date: 2026-07-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0019"
down_revision: Union[str, None] = ("0013", "0018")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
