"""alerts to notifications

Revision ID: 0070
Revises: 0069
Create Date: 2026-08-02

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0070"
down_revision: str | None = "0069"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.rename_table("alerts", "notifications")

    op.add_column("notifications", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("notifications", sa.Column("body", sa.String(length=1000), nullable=True))
    op.add_column("notifications", sa.Column("action_url", sa.String(length=500), nullable=True))
    op.add_column("notifications", sa.Column("action_label", sa.String(length=100), nullable=True))
    op.add_column("notifications", sa.Column("job_id", UUID(as_uuid=True), nullable=True))
    op.add_column("notifications", sa.Column("candidate_id", sa.Integer(), nullable=True))
    op.add_column("notifications", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("dedupe_key", sa.String(length=255), nullable=True))

    op.alter_column("notifications", "type", type_=sa.String(length=30), existing_type=sa.String(length=10))

    op.execute(
        """
        UPDATE notifications
        SET title = CASE type
                WHEN 'SLOTS' THEN 'Slot availability request'
                WHEN 'REVIEW' THEN 'Review pending'
                ELSE type
            END,
            action_url = CASE type
                WHEN 'SLOTS' THEN '/book-slot/' || form_id::text
                WHEN 'REVIEW' THEN '/rate-candidate/' || form_id::text
                ELSE NULL
            END,
            action_label = CASE type
                WHEN 'SLOTS' THEN 'Book slots'
                WHEN 'REVIEW' THEN 'Submit review'
                ELSE NULL
            END
        """
    )
    op.alter_column("notifications", "title", nullable=False)

    op.execute("ALTER TABLE notifications RENAME CONSTRAINT fk_alerts_employee_id TO fk_notifications_employee_id")
    op.execute("ALTER TABLE notifications RENAME CONSTRAINT fk_alerts_form_id TO fk_notifications_form_id")
    op.execute("ALTER TABLE notifications RENAME CONSTRAINT alerts_pkey TO notifications_pkey")

    op.drop_constraint("ck_alerts_type", "notifications", type_="check")

    op.add_column("users", sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"))
    op.execute(
        """
        UPDATE users u
        SET unread_count = (
            SELECT count(*) FROM notifications n
            WHERE n.employee_id = u.id AND n.is_read = false
        )
        """
    )

    op.create_index(
        "ix_notifications_employee_created",
        "notifications",
        ["employee_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_notifications_employee_dedupe
        ON notifications (employee_id, dedupe_key)
        WHERE dedupe_key IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_notifications_employee_dedupe")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_employee_created", table_name="notifications")

    op.drop_column("users", "unread_count")

    op.execute("ALTER TABLE notifications RENAME CONSTRAINT notifications_pkey TO alerts_pkey")
    op.execute("ALTER TABLE notifications RENAME CONSTRAINT fk_notifications_form_id TO fk_alerts_form_id")
    op.execute("ALTER TABLE notifications RENAME CONSTRAINT fk_notifications_employee_id TO fk_alerts_employee_id")

    op.alter_column("notifications", "title", nullable=True)
    op.drop_column("notifications", "dedupe_key")
    op.drop_column("notifications", "read_at")
    op.drop_column("notifications", "candidate_id")
    op.drop_column("notifications", "job_id")
    op.drop_column("notifications", "action_label")
    op.drop_column("notifications", "action_url")
    op.drop_column("notifications", "body")
    op.drop_column("notifications", "title")

    op.alter_column("notifications", "type", type_=sa.String(length=10), existing_type=sa.String(length=30))
    op.create_check_constraint("ck_alerts_type", "notifications", "type IN ('SLOTS', 'REVIEW')")
    op.rename_table("notifications", "alerts")
