"""slim users table — drop HR fields that now live on employees

Removes 14 HR/directory columns from ``users``. Auth-relevant columns
(id, emp_id, email, name, password_hash, auth_provider, tenant_id,
employee_id, is_active, status, role, unread_count, created_at) stay.

Downgrade re-adds the columns as nullable so old data would be lost
but the schema round-trips.

Revision ID: 0077
Revises: 0076
Create Date: 2026-08-04

"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0077"
down_revision: str | None = "0076"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


_DROPPED: tuple[str, ...] = (
    "personal_email",
    "user_type",
    "designation",
    "department",
    "phone_number",
    "work_mode",
    "delivery_status",
    "work_location_type",
    "doj",
    "doe",
    "date_of_birth",
    "internship_duration",
    "band",
    "skills",
)


def upgrade() -> None:
    for col in _DROPPED:
        op.drop_column("users", col)


def downgrade() -> None:
    op.add_column("users", sa.Column("personal_email", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("user_type", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("designation", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("department", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("phone_number", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("work_mode", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("delivery_status", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("work_location_type", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("doj", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("doe", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("internship_duration", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("band", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("skills", sa.Text(), nullable=True))
