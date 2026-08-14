"""add ping_a_verified / ping_b_verified to integration_link_flows

The live schema was created from an earlier revision of 0091 that predated the
mutual-ping proof flags; the ORM model (and current 0091) expect them. This adds
the two NOT NULL flags with a false server default.

Revision ID: 0092
Revises: 0091
Create Date: 2026-08-14
"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0092"
down_revision: str | None = "0091"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column(
        "integration_link_flows",
        sa.Column(
            "ping_a_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "integration_link_flows",
        sa.Column(
            "ping_b_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("integration_link_flows", "ping_b_verified")
    op.drop_column("integration_link_flows", "ping_a_verified")
