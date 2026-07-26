"""add org profile fields to tenants

Revision ID: 0050
Revises: 0049
Create Date: 2026-07-26

"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("logo_url", sa.String(500), nullable=True))
    op.add_column("tenants", sa.Column("website", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("tenants", sa.Column("description", sa.Text, nullable=True))
    op.add_column("tenants", sa.Column("address_line1", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("address_line2", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("tenants", sa.Column("state", sa.String(100), nullable=True))
    op.add_column("tenants", sa.Column("postal_code", sa.String(20), nullable=True))
    op.add_column("tenants", sa.Column("country", sa.String(100), nullable=True))
    op.add_column("tenants", sa.Column("gst_number", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "gst_number")
    op.drop_column("tenants", "country")
    op.drop_column("tenants", "postal_code")
    op.drop_column("tenants", "state")
    op.drop_column("tenants", "city")
    op.drop_column("tenants", "address_line2")
    op.drop_column("tenants", "address_line1")
    op.drop_column("tenants", "description")
    op.drop_column("tenants", "phone")
    op.drop_column("tenants", "website")
    op.drop_column("tenants", "logo_url")
