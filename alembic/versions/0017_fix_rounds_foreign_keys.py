"""Fix foreign keys on rounds table

- candidate_id -> candidates.application_id (was candidates.id)
- jd_id -> hiring_requests.supabase_job_id (was hiring_requests.id)
- Added unique constraint on hiring_requests.supabase_job_id (needed for FK)

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_hiring_requests_supabase_job_id",
        "hiring_requests",
        ["supabase_job_id"],
    )

    op.drop_constraint("rounds_candidate_id_fkey", "rounds", type_="foreignkey")
    op.drop_constraint("rounds_jd_id_fkey", "rounds", type_="foreignkey")

    op.alter_column(
        "rounds",
        "candidate_id",
        type_=sa.String(255),
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_foreign_key(
        "rounds_candidate_id_fkey",
        "rounds",
        "candidates",
        ["candidate_id"],
        ["application_id"],
    )
    op.create_foreign_key(
        "rounds_jd_id_fkey",
        "rounds",
        "hiring_requests",
        ["jd_id"],
        ["supabase_job_id"],
    )


def downgrade() -> None:
    op.drop_constraint("rounds_candidate_id_fkey", "rounds", type_="foreignkey")
    op.drop_constraint("rounds_jd_id_fkey", "rounds", type_="foreignkey")

    op.alter_column(
        "rounds",
        "candidate_id",
        type_=sa.Integer(),
        existing_type=sa.String(255),
        nullable=False,
    )

    op.create_foreign_key(
        "rounds_candidate_id_fkey",
        "rounds",
        "candidates",
        ["candidate_id"],
        ["id"],
    )
    op.create_foreign_key(
        "rounds_jd_id_fkey",
        "rounds",
        "hiring_requests",
        ["jd_id"],
        ["id"],
    )

    op.drop_constraint(
        "uq_hiring_requests_supabase_job_id",
        "hiring_requests",
        type_="unique",
    )
