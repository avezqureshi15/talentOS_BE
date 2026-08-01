"""tenant-scope hiring requests and add job-level roles

Revision ID: 0068
Revises: 0067
Create Date: 2026-08-01

"""
from alembic import op
import sqlalchemy as sa

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None

BACKFILL_TENANT_ID = 3


def upgrade() -> None:
    op.add_column("hiring_requests", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.create_index("ix_hiring_requests_tenant_id", "hiring_requests", ["tenant_id"])
    op.create_foreign_key(
        "fk_hiring_requests_tenant_id",
        "hiring_requests",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.execute(
        sa.text(
            "UPDATE hiring_requests SET tenant_id = :tenant_id WHERE tenant_id IS NULL"
        ).bindparams(tenant_id=BACKFILL_TENANT_ID)
    )

    op.add_column(
        "job_team_members",
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="recruiter",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE job_team_members SET role = :owner WHERE is_owner = TRUE"
        ).bindparams(owner="job_owner")
    )
    op.execute(
        sa.text("UPDATE job_team_members SET role = 'recruiter' WHERE is_owner = FALSE")
    )
    op.alter_column(
        "job_team_members",
        "role",
        existing_type=sa.String(length=20),
        server_default=None,
        nullable=False,
    )


def downgrade() -> None:
    op.drop_constraint("fk_hiring_requests_tenant_id", "hiring_requests", type_="foreignkey")
    op.drop_index("ix_hiring_requests_tenant_id", table_name="hiring_requests")
    op.drop_column("hiring_requests", "tenant_id")
    op.drop_column("job_team_members", "role")
