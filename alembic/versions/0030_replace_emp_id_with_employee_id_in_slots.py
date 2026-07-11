"""Replace slots.emp_id with slots.employee_id FK to users.id

Revision ID: 0030
Revises: 0029
Create Date: 2026-07-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the old FK on emp_id
    op.drop_constraint("fk_slots_emp_id_users", "slots", type_="foreignkey")

    # 2. Drop the index on emp_id
    op.drop_index("ix_slots_emp_id", table_name="slots")

    # 3. Drop the emp_id column
    op.drop_column("slots", "emp_id")

    # 4. Add employee_id column (nullable initially for backfill)
    op.add_column(
        "slots",
        sa.Column("employee_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_slots_employee_id_users",
        "slots",
        "users",
        ["employee_id"],
        ["id"],
    )
    op.create_index("ix_slots_employee_id", "slots", ["employee_id"])

    # 5. Backfill employee_id from users table for existing rows
    op.execute(
        """
        UPDATE slots
        SET employee_id = users.id
        FROM users
        WHERE slots.employee_id IS NULL
        AND users.emp_id IS NOT NULL
        """
    )

    # 6. Make employee_id NOT NULL
    op.alter_column("slots", "employee_id", nullable=False)


def downgrade() -> None:
    # 1. Drop FK and index on employee_id
    op.drop_index("ix_slots_employee_id", table_name="slots")
    op.drop_constraint("fk_slots_employee_id_users", "slots", type_="foreignkey")

    # 2. Drop employee_id column
    op.drop_column("slots", "employee_id")

    # 3. Re-add emp_id column
    op.add_column(
        "slots",
        sa.Column("emp_id", sa.String(length=50), nullable=False),
    )
    op.create_index("ix_slots_emp_id", "slots", ["emp_id"])
    op.create_foreign_key(
        "fk_slots_emp_id_users",
        "slots",
        "users",
        ["emp_id"],
        ["emp_id"],
    )
