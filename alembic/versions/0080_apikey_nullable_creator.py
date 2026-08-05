"""make api_keys.created_by_user_id nullable

An api-key-authenticated caller had a synthetic user id of `-api_key.id`,
which FK-violated on `users.id` when it tried to create another api key
(or any other row with a `created_by_user_id` FK). The router now sets
`created_by_user_id=None` for api-key callers, so the column must accept
NULL. Existing rows are untouched.

Revision ID: 0080
Revises: 0079
Create Date: 2026-08-05
"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0080"
down_revision: str | None = "0079"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.alter_column(
        "api_keys",
        "created_by_user_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    # Rows created after this migration may hold NULL; a naive re-enable of
    # NOT NULL would fail. Downgrade is a no-op — clean up NULLs manually
    # before re-tightening the constraint.
    pass
