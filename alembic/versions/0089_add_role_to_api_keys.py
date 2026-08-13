"""add role to api_keys

Adds a nullable ``role`` column so API keys can be assigned a tenant role
(account_admin / job_owner / recruiter / reviewer) whose permission preset
materializes into api_key_permissions. Existing keys stay role-less
(behave exactly as before).

Revision ID: 0089
Revises: 0088
Create Date: 2026-08-12

"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0089"
down_revision: str | None = "0088"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("role", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_api_keys_role", "api_keys", ["role"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_role", table_name="api_keys")
    op.drop_column("api_keys", "role")