"""add tenant_invites table

Revision ID: 0047
Revises: 0046
Create Date: 2026-07-23

"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_invites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("token", sa.String(255), nullable=False),
        sa.Column("invited_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_invites_token", "tenant_invites", ["token"], unique=True)
    op.create_index(
        "ix_tenant_invites_tenant_email_pending",
        "tenant_invites",
        ["tenant_id", "email"],
        postgresql_where=sa.text("accepted_at IS NULL"),
        mssql_where=sa.text("accepted_at IS NULL"),
        sqlite_where=sa.text("accepted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_invites_tenant_email_pending", table_name="tenant_invites")
    op.drop_index("ix_tenant_invites_token", table_name="tenant_invites")
    op.drop_table("tenant_invites")
