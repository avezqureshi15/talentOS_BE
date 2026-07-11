"""Add FK from slots.emp_id to users.emp_id

Revision ID: 0029
Revises: 0028
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_slots_emp_id_users",
        "slots",
        "users",
        ["emp_id"],
        ["emp_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_slots_emp_id_users", "slots", type_="foreignkey")
