"""add api_keys and api_key_permissions tables

Revision ID: 0055
Revises: 5d27bb707958
Create Date: 2026-07-29

"""
from alembic import op
import sqlalchemy as sa


revision = "0055"
down_revision = "5d27bb707958"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("key_hash", sa.String(length=255), nullable=False, index=True),
        sa.Column("key_prefix", sa.String(length=8), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"],),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_table(
        "api_key_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("api_key_id", sa.Integer(), nullable=False, index=True),
        sa.Column("permission_code", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"],),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key_id", "permission_code", name="uq_api_key_permission"),
    )


def downgrade() -> None:
    op.drop_table("api_key_permissions")
    op.drop_table("api_keys")
