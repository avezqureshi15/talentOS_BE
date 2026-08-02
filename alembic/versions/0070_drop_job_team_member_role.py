"""drop per-job role from job_team_members

Roles are now global-only: a user's effective permissions come from their
org role, and job_team_members is a plain membership list (visibility
scoping) with an is_owner flag.

Revision ID: 0070
Revises: 0069
Create Date: 2026-08-01

"""
from alembic import op
import sqlalchemy as sa

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("job_team_members", "role")


def downgrade() -> None:
    op.add_column(
        "job_team_members",
        sa.Column(
            "role",
            sa.String(length=20),
            server_default="recruiter",
            nullable=False,
        ),
    )
