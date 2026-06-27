"""Merge hiring_requests and resume_evaluations branches

Revision ID: 0008
Revises: 0006, 0007
Create Date: 2026-06-26 17:23:14.936626
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0008'
down_revision: Union[str, None] = ('0006', '0007')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
