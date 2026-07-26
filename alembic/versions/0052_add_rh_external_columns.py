"""add rh_external_job_id and rh_external_candidate_id columns

Revision ID: 0052
Revises: 0051
Create Date: 2026-07-26

"""
from alembic import op
import sqlalchemy as sa


revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hiring_requests", sa.Column("rh_external_job_id", sa.String(255), nullable=True))
    op.add_column("candidates", sa.Column("rh_external_candidate_id", sa.String(255), nullable=True))
    op.add_column("rounds", sa.Column("rh_external_session_id", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("rounds", "rh_external_session_id")
    op.drop_column("candidates", "rh_external_candidate_id")
    op.drop_column("hiring_requests", "rh_external_job_id")
