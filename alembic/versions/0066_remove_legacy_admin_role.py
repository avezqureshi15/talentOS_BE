"""remove legacy admin role entirely

Revision ID: 0066
Revises: 0065
Create Date: 2026-08-01

"""
from alembic import op
import sqlalchemy as sa

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("DELETE FROM role_permissions WHERE role_name = 'admin'"))
    conn.execute(sa.text("UPDATE users SET role = 'account_admin' WHERE role = 'admin'"))
    conn.execute(sa.text("UPDATE tenant_invites SET role = 'account_admin' WHERE role = 'admin'"))


def downgrade() -> None:
    pass
