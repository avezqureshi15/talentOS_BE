"""drop alerts.emp_id, add alerts.employee_id FK → users.id

Revision ID: 0039
Revises: 0038
Create Date: 2026-07-13

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("employee_id", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE alerts SET employee_id = users.id FROM users WHERE alerts.emp_id = users.emp_id"
    )
    op.alter_column("alerts", "employee_id", nullable=False)
    op.create_index("ix_alerts_employee_id", "alerts", ["employee_id"])
    op.create_foreign_key("fk_alerts_employee_id", "alerts", "users", ["employee_id"], ["id"])
    op.drop_column("alerts", "emp_id")


def downgrade() -> None:
    op.add_column("alerts", sa.Column("emp_id", sa.String(50), nullable=True))
    op.execute(
        "UPDATE alerts SET emp_id = users.emp_id FROM users WHERE alerts.employee_id = users.id"
    )
    op.alter_column("alerts", "emp_id", nullable=False)
    op.create_index("ix_alerts_emp_id", "alerts", ["emp_id"])
    op.drop_constraint("fk_alerts_employee_id", "alerts", type_="foreignkey")
    op.drop_index("ix_alerts_employee_id", table_name="alerts")
    op.drop_column("alerts", "employee_id")
