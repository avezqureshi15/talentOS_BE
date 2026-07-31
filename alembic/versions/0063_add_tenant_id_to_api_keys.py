"""add tenant_id to api_keys and api_key.manage permission

Revision ID: 0063
Revises: 0062
Create Date: 2026-07-31

"""
from alembic import op
import sqlalchemy as sa


revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_foreign_key(
        "fk_api_keys_tenant_id_tenants",
        "api_keys",
        "tenants",
        ["tenant_id"],
        ["id"],
    )

    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM permissions WHERE code = 'api_key.manage'")
    ).scalar()
    if not exists:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, name, \"group\", endpoint, is_default) "
                "VALUES ('api_key.manage', 'Api Key Manage', 'tenant', "
                "'GET /api/v1/admin/apps, POST /api/v1/admin/apps', true)"
            )
        )
    for role in ("admin", "superadmin"):
        conn.execute(
            sa.text(
                "INSERT INTO role_permissions (role_name, permission_code) "
                "SELECT :role, 'api_key.manage' WHERE NOT EXISTS ("
                "  SELECT 1 FROM role_permissions "
                "  WHERE role_name = :role AND permission_code = 'api_key.manage')"
            ).bindparams(role=role)
        )


def downgrade() -> None:
    op.drop_constraint("fk_api_keys_tenant_id_tenants", "api_keys", type_="foreignkey")
    op.drop_index("ix_api_keys_tenant_id", table_name="api_keys")
    op.drop_column("api_keys", "tenant_id")

    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_code = 'api_key.manage'")
    )
    conn.execute(
        sa.text("DELETE FROM permissions WHERE code = 'api_key.manage'")
    )
