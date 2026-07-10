"""Refactor slots ownership and add forms/alerts tables

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    slots_columns = {col["name"] for col in inspector.get_columns("slots")}

    if "emp_id" not in slots_columns:
        op.add_column("slots", sa.Column("emp_id", sa.String(length=50), nullable=True))
        op.create_index("ix_slots_emp_id", "slots", ["emp_id"])
        op.create_index("ix_slots_emp_id_start_at", "slots", ["emp_id", "start_at"])

        op.execute(
            """
            UPDATE slots s
            SET emp_id = sch.emp_id
            FROM (
                SELECT emp_id, unnest(slot_ids) AS slot_id
                FROM schedules
            ) sch
            WHERE s.id = sch.slot_id
            """
        )
        op.execute("DELETE FROM slots WHERE emp_id IS NULL")
        op.alter_column("slots", "emp_id", nullable=False)

        if inspector.has_table("schedules"):
            try:
                op.drop_index("ix_schedules_emp_id", table_name="schedules")
            except Exception:
                pass
            op.drop_table("schedules")

    if not inspector.has_table("forms"):
        op.create_table(
            "forms",
            sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
            sa.Column("emp_id", sa.String(length=50), nullable=False),
            sa.Column("type", sa.String(length=10), nullable=False, server_default="SLOTS"),
            sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("type IN ('SLOTS', 'REVIEW')", name="ck_forms_type"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("emp_id", "type", name="uq_forms_emp_id_type"),
        )
        op.create_index("ix_forms_emp_id", "forms", ["emp_id"])
        op.create_index("ix_forms_emp_id_type", "forms", ["emp_id", "type"])

    if not inspector.has_table("alerts"):
        op.create_table(
            "alerts",
            sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
            sa.Column("emp_id", sa.String(length=50), nullable=False),
            sa.Column("type", sa.String(length=10), nullable=False, server_default="SLOTS"),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("type IN ('SLOTS', 'REVIEW')", name="ck_alerts_type"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_alerts_type_is_read_created_at", "alerts", ["type", "is_read", "created_at"])
        op.create_index("ix_alerts_emp_id_type_is_read", "alerts", ["emp_id", "type", "is_read"])


def downgrade() -> None:
    op.drop_index("ix_alerts_emp_id_type_is_read", table_name="alerts")
    op.drop_index("ix_alerts_type_is_read_created_at", table_name="alerts")
    op.drop_table("alerts")

    op.drop_index("ix_forms_emp_id_type", table_name="forms")
    op.drop_index("ix_forms_emp_id", table_name="forms")
    op.drop_table("forms")

    op.create_table(
        "schedules",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("emp_id", sa.String(length=50), nullable=False),
        sa.Column("slot_ids", sa.ARRAY(sa.Uuid()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("emp_id"),
    )
    op.create_index("ix_schedules_emp_id", "schedules", ["emp_id"])

    op.execute(
        """
        INSERT INTO schedules (id, emp_id, slot_ids, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            emp_id,
            array_agg(id ORDER BY start_at),
            now(),
            now()
        FROM slots
        GROUP BY emp_id
        """
    )

    op.drop_index("ix_slots_emp_id_start_at", table_name="slots")
    op.drop_index("ix_slots_emp_id", table_name="slots")
    op.drop_column("slots", "emp_id")
