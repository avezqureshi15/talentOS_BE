"""Fix rounds foreign keys to point to PKs

- candidate_id -> candidates.id (was candidates.application_id)
- jd_id -> hiring_requests.id (was hiring_requests.supabase_job_id)
- Dropped unique constraint on hiring_requests.supabase_job_id (no longer needed for FK)

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for fk in inspector.get_foreign_keys("rounds"):
        if fk["name"] == "rounds_candidate_id_fkey":
            op.drop_constraint("rounds_candidate_id_fkey", "rounds", type_="foreignkey")
        elif fk["name"] == "rounds_jd_id_fkey":
            op.drop_constraint("rounds_jd_id_fkey", "rounds", type_="foreignkey")

    unique_constraints = [c["name"] for c in inspector.get_unique_constraints("hiring_requests")]
    if "uq_hiring_requests_supabase_job_id" in unique_constraints:
        op.drop_constraint("uq_hiring_requests_supabase_job_id", "hiring_requests", type_="unique")

    rounds_columns = {col["name"]: col for col in inspector.get_columns("rounds")}
    if isinstance(rounds_columns["candidate_id"]["type"], sa.String):
        op.alter_column(
            "rounds",
            "candidate_id",
            type_=sa.Integer(),
            existing_type=sa.String(255),
            nullable=False,
            postgresql_using="candidate_id::integer",
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


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for fk in inspector.get_foreign_keys("rounds"):
        if fk["name"] == "rounds_candidate_id_fkey":
            op.drop_constraint("rounds_candidate_id_fkey", "rounds", type_="foreignkey")
        elif fk["name"] == "rounds_jd_id_fkey":
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

    unique_constraints = [c["name"] for c in inspector.get_unique_constraints("hiring_requests")]
    if "uq_hiring_requests_supabase_job_id" not in unique_constraints:
        op.create_unique_constraint(
            "uq_hiring_requests_supabase_job_id",
            "hiring_requests",
            ["supabase_job_id"],
        )
