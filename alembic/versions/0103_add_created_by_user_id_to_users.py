"""Add created_by_user_id to users

Tracks who created each account (direct admin-create, or whoever sent the
accepted invite) so superadmin's user list can be scoped to only users they
personally created/invited, instead of every user across every tenant —
otherwise superadmin can browse any org's full user directory, which is a
privacy violation for tenant orgs. Null for self-service signup / Google
first-login users, and for all pre-existing rows (they predate this
attribution and won't retroactively appear in any superadmin's filtered view).

Revision ID: 0103
Revises: 0102
Create Date: 2026-09-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0103"
down_revision: Union[str, None] = "0102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("users")}

    if "created_by_user_id" not in existing:
        op.add_column(
            "users",
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_users_created_by_user_id",
            "users",
            "users",
            ["created_by_user_id"],
            ["id"],
        )


def downgrade() -> None:
    op.drop_constraint("fk_users_created_by_user_id", "users", type_="foreignkey")
    op.drop_column("users", "created_by_user_id")
