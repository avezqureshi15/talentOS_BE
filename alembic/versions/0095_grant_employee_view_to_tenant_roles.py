"""grant employee.view to all tenant roles

employee.view has been in app.core.permissions.DEFAULT_ROLE_PERMISSIONS for
account_admin/job_owner/recruiter/reviewer since it was introduced, but the
0065 RBAC migration that seeded role_permissions never included it — so
every tenant's DB-backed grants have been missing it (PermissionService only
falls back to the code default when a role has zero DB rows).

Revision ID: 0095
Revises: 0094
Create Date: 2026-09-03

"""
from alembic import op
import sqlalchemy as sa

revision = "0095"
down_revision = "0094"
branch_labels = None
depends_on = None

ROLES = ("account_admin", "job_owner", "recruiter", "reviewer")
EMPLOYEE_VIEW = "employee.view"


def upgrade() -> None:
    for role in ROLES:
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (role_name, permission_code) "
                "SELECT :role, :perm WHERE NOT EXISTS ("
                "  SELECT 1 FROM role_permissions "
                "  WHERE role_name = :role AND permission_code = :perm"
                ")"
            ).bindparams(role=role, perm=EMPLOYEE_VIEW)
        )


def downgrade() -> None:
    for role in ROLES:
        op.execute(
            sa.text(
                "DELETE FROM role_permissions "
                "WHERE role_name = :role AND permission_code = :perm"
            ).bindparams(role=role, perm=EMPLOYEE_VIEW)
        )
