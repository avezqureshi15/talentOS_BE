"""add platform_settings table

Revision ID: 0083
Revises: 0082
Create Date: 2026-08-10

"""
from alembic import op
import sqlalchemy as sa


revision = "0083"
down_revision = "0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_platform_setting_key"),
    )

    # SERVICE_API_KEY moved from tenant scope to platform (global) scope —
    # inbound callbacks have no tenant context, so copy the first tenant value
    # to the new platform store and drop the tenant rows.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT tenant_id, value FROM tenant_settings "
            "WHERE key = 'SERVICE_API_KEY' ORDER BY id ASC"
        )
    ).fetchall()
    if rows:
        bind.execute(
            sa.text("INSERT INTO platform_settings (key, value, updated_at) VALUES ('SERVICE_API_KEY', :value, now())"),
            {"value": rows[0][1]},
        )
        bind.execute(sa.text("DELETE FROM tenant_settings WHERE key = 'SERVICE_API_KEY'"))


def downgrade() -> None:
    op.drop_table("platform_settings")