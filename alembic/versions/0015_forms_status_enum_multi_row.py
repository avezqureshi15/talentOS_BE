"""Forms status string enum and multi-row per employee

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_forms_emp_id_type", "forms", type_="unique")

    op.add_column("forms", sa.Column("status_new", sa.String(length=10), nullable=True))
    op.execute("UPDATE forms SET status_new = CASE WHEN status = true THEN 'SUBMITTED' ELSE 'SENT' END")
    op.drop_column("forms", "status")
    op.alter_column("forms", "status_new", new_column_name="status", nullable=False)
    op.create_check_constraint(
        "ck_forms_status",
        "forms",
        "status IN ('SENT', 'SUBMITTED', 'EXPIRED')",
    )

    op.create_index(
        "ix_forms_emp_id_type_last_sent",
        "forms",
        ["emp_id", "type", "last_sent_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_forms_emp_id_type_last_sent", table_name="forms")
    op.drop_constraint("ck_forms_status", "forms", type_="check")

    op.add_column("forms", sa.Column("status_old", sa.Boolean(), nullable=True))
    op.execute(
        "UPDATE forms SET status_old = CASE WHEN status = 'SUBMITTED' THEN true ELSE false END"
    )
    op.drop_column("forms", "status")
    op.alter_column("forms", "status_old", new_column_name="status", nullable=False)

    op.create_unique_constraint("uq_forms_emp_id_type", "forms", ["emp_id", "type"])
