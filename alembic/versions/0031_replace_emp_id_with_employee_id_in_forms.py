"""Replace forms.emp_id with forms.employee_id FK to users.id

Revision ID: 0031
Revises: 0030
Create Date: 2026-07-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add employee_id column (nullable initially for backfill)
    op.add_column(
        "forms",
        sa.Column("employee_id", sa.Integer(), nullable=True),
    )

    # 2. Backfill employee_id from users table
    op.execute(
        """
        UPDATE forms
        SET employee_id = users.id
        FROM users
        WHERE forms.employee_id IS NULL
        AND users.emp_id = forms.emp_id
        """
    )

    # 3. Drop old indexes referencing emp_id
    op.drop_index("ix_forms_emp_id_type_last_sent", table_name="forms")
    op.drop_index("ix_forms_emp_id_type", table_name="forms")
    op.drop_index("ix_forms_emp_id", table_name="forms")

    # 4. Drop the old emp_id column
    op.drop_column("forms", "emp_id")

    # 5. Create FK and index on employee_id
    op.create_foreign_key(
        "fk_forms_employee_id_users",
        "forms",
        "users",
        ["employee_id"],
        ["id"],
    )
    op.create_index("ix_forms_employee_id", "forms", ["employee_id"])

    # 6. Make employee_id NOT NULL
    op.alter_column("forms", "employee_id", nullable=False)


def downgrade() -> None:
    # 1. Drop FK and index on employee_id
    op.drop_index("ix_forms_employee_id", table_name="forms")
    op.drop_constraint("fk_forms_employee_id_users", "forms", type_="foreignkey")

    # 2. Drop employee_id column
    op.drop_column("forms", "employee_id")

    # 3. Re-add emp_id column
    op.add_column(
        "forms",
        sa.Column("emp_id", sa.String(length=50), nullable=False),
    )
    op.create_index("ix_forms_emp_id", "forms", ["emp_id"])
    op.create_index("ix_forms_emp_id_type", "forms", ["emp_id", "type"])
    op.create_index(
        "ix_forms_emp_id_type_last_sent", "forms", ["emp_id", "type", "last_sent_at"]
    )
