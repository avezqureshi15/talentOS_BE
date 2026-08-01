"""remove legacy hr and viewer roles entirely

Revision ID: 0067
Revises: 0066
Create Date: 2026-08-01

"""
from alembic import op
import sqlalchemy as sa

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None

ALLOWED_ROLES = (
    "superadmin",
    "account_admin",
    "job_owner",
    "recruiter",
    "reviewer",
)


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("DELETE FROM role_permissions WHERE role_name IN ('hr', 'viewer')"))
    conn.execute(sa.text("DELETE FROM roles WHERE role_name IN ('hr', 'viewer')"))

    conn.execute(sa.text("UPDATE users SET role = 'recruiter' WHERE role = 'hr'"))
    conn.execute(sa.text("UPDATE users SET role = 'reviewer' WHERE role = 'viewer'"))
    conn.execute(sa.text("UPDATE users SET role = 'reviewer' WHERE COALESCE(role, '') NOT IN :allowed").bindparams(
        allowed=tuple(ALLOWED_ROLES)
    ))

    conn.execute(sa.text("UPDATE tenant_invites SET role = 'recruiter' WHERE role = 'hr'"))
    conn.execute(sa.text("UPDATE tenant_invites SET role = 'reviewer' WHERE role = 'viewer'"))
    conn.execute(sa.text("UPDATE tenant_invites SET role = 'reviewer' WHERE COALESCE(role, '') NOT IN :allowed").bindparams(
        allowed=tuple(ALLOWED_ROLES)
    ))


def downgrade() -> None:
    pass
