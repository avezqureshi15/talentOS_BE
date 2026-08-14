"""add integration_links, integration_link_flows, integration_link_events

One-click connect: durable relationship (link) + per-operation attempts (flow)
+ append-only audit (event). Tenants get nullable external_platform /
external_tenant_id with a partial unique index (NULL rows never collide).

Revision ID: 0091
Revises: 0090
Create Date: 2026-08-13

"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0091"
down_revision: str | None = "0090"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.create_table(
        "integration_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("external_tenant_id", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("current_flow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rhub_key_id", sa.String(length=255), nullable=True),
        sa.Column("tal_key_id", sa.Integer(), nullable=True),
        sa.Column("rhub_key_enc", sa.Text(), nullable=True),
        sa.Column("tal_key_enc", sa.Text(), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tal_key_id"], ["api_keys.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "tenant_id", name="uq_integration_link_provider_tenant"
        ),
    )
    op.create_index(
        "uq_integration_links_current_flow",
        "integration_links",
        ["current_flow_id"],
        unique=True,
        postgresql_where=sa.text("current_flow_id IS NOT NULL"),
    )
    op.create_index(
        "ix_integration_links_tenant_id",
        "integration_links",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "integration_link_flows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("flow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("link_id", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("ping_a_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ping_b_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["link_id"], ["integration_links.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flow_id", name="uq_integration_link_flow_flow_id"),
    )
    op.create_index(
        "ix_integration_link_flows_state_retry",
        "integration_link_flows",
        ["state", "next_retry_at"],
        unique=False,
    )

    op.create_table(
        "integration_link_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("link_id", sa.Integer(), nullable=False),
        sa.Column("flow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["link_id"], ["integration_links.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_integration_link_events_link_id",
        "integration_link_events",
        ["link_id"],
        unique=False,
    )

    op.add_column(
        "tenants",
        sa.Column("external_platform", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("external_tenant_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "uq_tenants_external_link",
        "tenants",
        ["external_platform", "external_tenant_id"],
        unique=True,
        postgresql_where=sa.text("external_platform IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_tenants_external_link", table_name="tenants")
    op.drop_column("tenants", "external_tenant_id")
    op.drop_column("tenants", "external_platform")

    op.drop_index("ix_integration_link_events_link_id", table_name="integration_link_events")
    op.drop_table("integration_link_events")

    op.drop_index("ix_integration_link_flows_state_retry", table_name="integration_link_flows")
    op.drop_table("integration_link_flows")

    op.drop_index("ix_integration_links_tenant_id", table_name="integration_links")
    op.drop_index("uq_integration_links_current_flow", table_name="integration_links")
    op.drop_table("integration_links")
