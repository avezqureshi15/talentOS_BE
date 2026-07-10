"""Create rounds, round_interviewers, and reviews tables

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rounds",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("jd_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("ai_verdict", sa.Text(), nullable=True),
        sa.Column("hr_verdict", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"],
            ["slots.id"],
        ),
        sa.ForeignKeyConstraint(
            ["jd_id"],
            ["hiring_requests.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "round_interviewers",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("round_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["rounds.id"],
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("round_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["rounds.id"],
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_table("round_interviewers")
    op.drop_table("rounds")
