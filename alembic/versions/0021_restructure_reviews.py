"""Remove ai_verdict/hr_verdict from rounds, verdict from round_interviewers, restructure reviews

- rounds: drop ai_verdict, hr_verdict
- round_interviewers: drop verdict
- reviews: drop summary, status; add entity_type, reviews, verdict; make employee_id nullable

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === rounds ===
    op.drop_column("rounds", "ai_verdict")
    op.drop_column("rounds", "hr_verdict")

    # === round_interviewers ===
    op.drop_column("round_interviewers", "verdict")

    # === reviews ===
    op.drop_column("reviews", "summary")
    op.drop_column("reviews", "status")

    op.add_column("reviews", sa.Column("entity_type", sa.String(length=50), nullable=False, server_default="INTERVIEWER"))
    op.add_column("reviews", sa.Column("reviews", sa.Text(), nullable=True))
    op.add_column("reviews", sa.Column("verdict", sa.String(length=50), nullable=True))

    op.alter_column("reviews", "employee_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # === reviews ===
    op.alter_column("reviews", "employee_id", existing_type=sa.Integer(), nullable=False)

    op.drop_column("reviews", "verdict")
    op.drop_column("reviews", "reviews")
    op.drop_column("reviews", "entity_type")

    op.add_column("reviews", sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"))
    op.add_column("reviews", sa.Column("summary", sa.Text(), nullable=True))

    # === round_interviewers ===
    op.add_column("round_interviewers", sa.Column("verdict", sa.Text(), nullable=True))

    # === rounds ===
    op.add_column("rounds", sa.Column("hr_verdict", sa.Text(), nullable=True))
    op.add_column("rounds", sa.Column("ai_verdict", sa.Text(), nullable=True))
