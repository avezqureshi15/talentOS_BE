"""Create resume_evaluations table

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.String(length=255), nullable=False),
        sa.Column("job_id", sa.String(length=255), nullable=False),
        sa.Column("candidate_name", sa.String(length=255), nullable=True),
        sa.Column("candidate_email", sa.String(length=255), nullable=True),
        sa.Column("resume_url", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="QUEUED"),
        sa.Column("fit_score", sa.Integer(), nullable=True),
        sa.Column("summary_md", sa.Text(), nullable=True),
        sa.Column("ats_threshold_used", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_resume_evaluations_application_id"),
    )
    op.create_index("ix_resume_evaluations_application_id", "resume_evaluations", ["application_id"])
    op.create_index("ix_resume_evaluations_job_id", "resume_evaluations", ["job_id"])
    op.create_index("ix_resume_evaluations_status", "resume_evaluations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_resume_evaluations_status", table_name="resume_evaluations")
    op.drop_index("ix_resume_evaluations_job_id", table_name="resume_evaluations")
    op.drop_index("ix_resume_evaluations_application_id", table_name="resume_evaluations")
    op.drop_table("resume_evaluations")
