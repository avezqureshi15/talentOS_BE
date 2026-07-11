"""Make round candidate_id slot_id jd_id nullable

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("rounds") as batch_op:
        batch_op.alter_column("candidate_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("slot_id", existing_type=sa.Uuid(), nullable=True)
        batch_op.alter_column("jd_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("rounds") as batch_op:
        batch_op.alter_column("candidate_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("slot_id", existing_type=sa.Uuid(), nullable=False)
        batch_op.alter_column("jd_id", existing_type=sa.Uuid(), nullable=False)
