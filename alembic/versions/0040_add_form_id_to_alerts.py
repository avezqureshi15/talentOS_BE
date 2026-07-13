"""add form_id column to alerts table

Revision ID: 0040
Revises: 0039
Create Date: 2026-07-13

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("form_id", UUID(as_uuid=True), nullable=True))
    op.execute(
        """
        UPDATE alerts
        SET form_id = subq.form_id
        FROM (
            SELECT DISTINCT ON (a.id)
                   a.id AS alert_id,
                   f.id  AS form_id
            FROM alerts a
            JOIN users u ON u.id = a.employee_id
            JOIN forms f ON f.employee_id = u.id
                       AND f.type = a.type
                       AND f.last_sent_at <= a.created_at
            WHERE a.form_id IS NULL
            ORDER BY a.id, f.last_sent_at DESC
        ) subq
        WHERE alerts.id = subq.alert_id
        """
    )
    op.create_foreign_key("fk_alerts_form_id", "alerts", "forms", ["form_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_alerts_form_id", "alerts", type_="foreignkey")
    op.drop_column("alerts", "form_id")
