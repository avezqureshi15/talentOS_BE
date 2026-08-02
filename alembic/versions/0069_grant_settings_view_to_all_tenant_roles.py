"""grant settings.view to all tenant roles

Revision ID: 0069
Revises: 0068
Create Date: 2026-08-01

"""
from alembic import op
import sqlalchemy as sa

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None

ROLES = ("job_owner", "recruiter", "reviewer")
SETTINGS_VIEW = "settings.view"


def upgrade() -> None:
    for role in ROLES:
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (role_name, permission_code) "
                "SELECT :role, :perm WHERE NOT EXISTS ("
                "  SELECT 1 FROM role_permissions "
                "  WHERE role_name = :role AND permission_code = :perm"
                ")"
            ).bindparams(role=role, perm=SETTINGS_VIEW)
        )


def downgrade() -> None:
    for role in ROLES:
        op.execute(
            sa.text(
                "DELETE FROM role_permissions "
                "WHERE role_name = :role AND permission_code = :perm"
            ).bindparams(role=role, perm=SETTINGS_VIEW)
        )
