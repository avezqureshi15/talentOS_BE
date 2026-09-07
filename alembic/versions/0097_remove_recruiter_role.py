"""Remove recruiter persona

recruiter is dropped from the platform. Existing users/invites holding that
role are moved up to job_owner (recruiter's permission set was effectively a
subset of job_owner's, so this preserves their access rather than gutting
it) instead of down to reviewer, which is the conservative default used for
brand-new users going forward.

Revision ID: 0097
Revises: 0093
Create Date: 2026-09-03

"""
from alembic import op
import sqlalchemy as sa

revision = "0097"
down_revision = "0093"
branch_labels = None
depends_on = None

REPLACEMENT_ROLE = "job_owner"

# Recruiter's permission set at the time of removal (see the 0065/0090
# migrations) — restored on downgrade so the role behaves the same as before
# this migration, though users/invites reassigned by upgrade() are not moved
# back (their original role is not recoverable).
RECRUITER_PERMISSIONS = [
    "application.view", "application.evaluate", "application.reject",
    "application.workflow", "hiring_request.edit", "hiring_request.view",
    "slot.view_all", "review.submit", "review.view_all", "report.export",
    "settings.view", "employee.view", "chat",
]


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE users SET role = :new_role WHERE role = 'recruiter'")
        .bindparams(new_role=REPLACEMENT_ROLE)
    )
    op.execute(
        sa.text("UPDATE tenant_invites SET role = :new_role WHERE role = 'recruiter'")
        .bindparams(new_role=REPLACEMENT_ROLE)
    )
    op.execute(sa.text("DELETE FROM role_permissions WHERE role_name = 'recruiter'"))
    op.execute(sa.text("DELETE FROM roles WHERE role_name = 'recruiter'"))


def downgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO roles (role_name, description, is_system) "
            "VALUES ('recruiter', 'Manages candidates and application workflow', true) "
            "ON CONFLICT (role_name) DO NOTHING"
        )
    )
    for code in RECRUITER_PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (role_name, permission_code) "
                "SELECT 'recruiter', :code WHERE NOT EXISTS ("
                "  SELECT 1 FROM role_permissions "
                "  WHERE role_name = 'recruiter' AND permission_code = :code)"
            ).bindparams(code=code)
        )
    # Users/invites moved to job_owner by upgrade() are intentionally left as
    # job_owner — which of them were originally recruiter is not recoverable.
