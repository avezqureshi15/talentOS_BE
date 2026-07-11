"""Create interviews table

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interviews",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("round_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("interviewer_id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("event_id", sa.String(length=500), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="SCHEDULED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["round_id"], ["rounds.id"],),
        sa.ForeignKeyConstraint(["interviewer_id"], ["users.id"],),
        sa.ForeignKeyConstraint(["slot_id"], ["slots.id"],),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("interviews")
