"""Add candidate detail columns to resume_evaluations

Revision ID: 0007
Revises: 0005b
Create Date: 2026-06-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0005b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("resume_evaluations", sa.Column("current_ctc", sa.String(length=50), nullable=True))
    op.add_column("resume_evaluations", sa.Column("expected_ctc", sa.String(length=50), nullable=True))
    op.add_column("resume_evaluations", sa.Column("location", sa.String(length=255), nullable=True))
    op.add_column("resume_evaluations", sa.Column("years_of_experience", sa.String(length=10), nullable=True))
    op.add_column("resume_evaluations", sa.Column("notice_period", sa.String(length=50), nullable=True))
    op.add_column("resume_evaluations", sa.Column("how_did_you_hear", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("resume_evaluations", "how_did_you_hear")
    op.drop_column("resume_evaluations", "notice_period")
    op.drop_column("resume_evaluations", "years_of_experience")
    op.drop_column("resume_evaluations", "location")
    op.drop_column("resume_evaluations", "expected_ctc")
    op.drop_column("resume_evaluations", "current_ctc")
