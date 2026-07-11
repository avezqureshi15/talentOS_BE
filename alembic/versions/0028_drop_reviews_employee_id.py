"""Drop employee_id column from reviews table

Revision ID: 0028
Revises: 0027
Create Date: 2026-07-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("reviews") as batch_op:
        batch_op.drop_column("employee_id")


def downgrade() -> None:
    with op.batch_alter_table("reviews") as batch_op:
        batch_op.add_column(sa.Column("employee_id", sa.Integer(), nullable=True))
