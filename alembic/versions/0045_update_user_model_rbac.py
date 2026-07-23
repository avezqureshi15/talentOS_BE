"""update user model for rbac

Revision ID: 0045
Revises: 0044
Create Date: 2026-07-23

"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("auth_provider", sa.String(20), nullable=False, server_default="google"))
    op.add_column("users", sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))

    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_column("users", "is_active")
    op.drop_column("users", "tenant_id")
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "password_hash")
