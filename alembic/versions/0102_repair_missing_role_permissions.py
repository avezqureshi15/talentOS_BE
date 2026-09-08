"""Repair missing role_permissions grants

Found live: production's account_admin (1 row) and reviewer (1 row) had only
the employee.view grant from migration 0095 — the rest of their permissions
were gone (role_permissions has no history/audit trail to say how; job_owner
was also short by at least one row). Since PermissionService only falls back
to the in-code DEFAULT_ROLE_PERMISSIONS when a role has *zero* rows, a
partially-populated role silently locks users out of everything not in that
partial set instead of falling back — this shipped as an account_admin user
who could see almost nothing after logging in.

Re-asserts the full current DEFAULT_ROLE_PERMISSIONS (app/core/permissions.py)
for account_admin/job_owner/reviewer via INSERT ... WHERE NOT EXISTS, so this
is safe to run against any environment regardless of what it's currently
missing. superadmin is intentionally left alone (0 rows -> fallback to "all
permissions" by design).

Revision ID: 0102
Revises: 0101
Create Date: 2026-09-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0102"
down_revision = "0101"
branch_labels = None
depends_on = None

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "account_admin": [
        "application.view", "application.evaluate", "application.reject",
        "application.workflow", "hiring_request.create", "hiring_request.edit",
        "hiring_request.view", "hiring_request.delete", "user.invite",
        "user.manage", "employee.view", "api_key.manage", "settings.view",
        "settings.edit", "slot.view_all", "review.submit", "review.view_all",
        "report.export", "interview.plan_edit", "job.team_manage", "chat",
    ],
    "job_owner": [
        "application.view", "application.evaluate", "application.reject",
        "application.workflow", "hiring_request.create", "hiring_request.edit",
        "hiring_request.view", "slot.view_all", "review.submit",
        "review.view_all", "report.export", "interview.plan_edit",
        "job.team_manage", "settings.view", "employee.view", "chat",
    ],
    "reviewer": [
        "application.view", "hiring_request.view", "report.export",
        "settings.view", "employee.view", "chat",
    ],
}


def upgrade() -> None:
    for role, codes in ROLE_PERMISSIONS.items():
        for code in codes:
            op.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_name, permission_code) "
                    "SELECT :role, :code WHERE NOT EXISTS ("
                    "  SELECT 1 FROM role_permissions "
                    "  WHERE role_name = :role AND permission_code = :code)"
                ).bindparams(role=role, code=code)
            )


def downgrade() -> None:
    # Data repair — not reversible (we don't know which rows pre-existed vs
    # which this migration added).
    pass
