"""Create users table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("emp_id", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("personal_email", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("user_type", sa.String(length=50), nullable=False),
        sa.Column("designation", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=255), nullable=False),
        sa.Column("phone_number", sa.String(length=20), nullable=True),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("work_mode", sa.String(length=50), nullable=False),
        sa.Column("delivery_status", sa.String(length=50), nullable=False),
        sa.Column("work_location_type", sa.String(length=50), nullable=False),
        sa.Column("doj", sa.Date(), nullable=False),
        sa.Column("doe", sa.Date(), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("internship_duration", sa.Integer(), nullable=True),
        sa.Column("band", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("emp_id"),
        sa.UniqueConstraint("email"),
    )


def downgrade() -> None:
    op.drop_table("users")
