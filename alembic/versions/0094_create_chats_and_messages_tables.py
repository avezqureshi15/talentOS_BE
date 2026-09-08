"""Create chats and messages tables

Guarded with has_table/get_indexes checks: at least one deployed environment
already had a "chats" table (auto-created long ago by the app's old
Base.metadata.create_all() dev fallback, before Alembic tracked it), so a
bare create_table failed with DuplicateTable and aborted the whole upgrade
chain there — which is exactly what happened in production.

Revision ID: 0094
Revises: 0093
Create Date: 2026-09-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0094"
down_revision: Union[str, None] = "0093"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("chats"):
        op.create_table(
            "chats",
            sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if "ix_chats_user_id" not in {ix["name"] for ix in inspector.get_indexes("chats")}:
        op.create_index("ix_chats_user_id", "chats", ["user_id"])

    if not inspector.has_table("messages"):
        op.create_table(
            "messages",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("chat_id", sa.Uuid(as_uuid=True), nullable=False),
            sa.Column("role", sa.String(length=50), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
        )
    if "ix_messages_chat_id" not in {ix["name"] for ix in inspector.get_indexes("messages")}:
        op.create_index("ix_messages_chat_id", "messages", ["chat_id"])


def downgrade() -> None:
    op.drop_index("ix_messages_chat_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_chats_user_id", table_name="chats")
    op.drop_table("chats")
