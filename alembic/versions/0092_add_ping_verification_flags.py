"""add ping_a_verified / ping_b_verified to integration_link_flows

The live schema was created from an earlier revision of 0091 that predated the
mutual-ping proof flags; the ORM model (and current 0091) expect them. This adds
the two NOT NULL flags with a false server default. Guarded so it is idempotent:
current 0091 already adds these columns in create_table, so skip if present.

Revision ID: 0092
Revises: 0091
Create Date: 2026-08-14
"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.engine import Connection

revision: str = "0092"
down_revision: str | None = "0091"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def _column_exists(table: str, column: str) -> bool:
    bind: Connection = op.get_bind()
    return column in {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    added = False
    if not _column_exists("integration_link_flows", "ping_a_verified"):
        op.add_column(
            "integration_link_flows",
            sa.Column(
                "ping_a_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
        added = True
    if not _column_exists("integration_link_flows", "ping_b_verified"):
        op.add_column(
            "integration_link_flows",
            sa.Column(
                "ping_b_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
        added = True
    if not added:
        # nothing to change; still run through the OP so the revision is stamped
        bind: Connection = op.get_bind()
        bind.exec_driver_sql("SELECT 1")


def downgrade() -> None:
    op.drop_column("integration_link_flows", "ping_b_verified")
    op.drop_column("integration_link_flows", "ping_a_verified")