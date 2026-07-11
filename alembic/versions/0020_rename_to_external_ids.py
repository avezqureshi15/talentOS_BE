"""Rename supabase_job_id / application_id / job_id to external_* for clarity

- hiring_requests.supabase_job_id  -> external_job_id
- candidates.job_id                -> external_job_id
- candidates.application_id        -> external_application_id

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("hiring_requests", "supabase_job_id", new_column_name="external_job_id")
    op.alter_column("candidates", "job_id", new_column_name="external_job_id")
    op.alter_column("candidates", "application_id", new_column_name="external_application_id")


def downgrade() -> None:
    op.alter_column("candidates", "external_application_id", new_column_name="application_id")
    op.alter_column("candidates", "external_job_id", new_column_name="job_id")
    op.alter_column("hiring_requests", "external_job_id", new_column_name="supabase_job_id")
