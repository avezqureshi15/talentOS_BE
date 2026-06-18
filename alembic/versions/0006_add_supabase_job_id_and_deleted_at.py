"""Add supabase_job_id and deleted_at to hiring_requests

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hiring_requests", sa.Column("supabase_job_id", sa.Uuid(as_uuid=True), nullable=True))
    op.add_column("hiring_requests", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("hiring_requests", "deleted_at")
    op.drop_column("hiring_requests", "supabase_job_id")
