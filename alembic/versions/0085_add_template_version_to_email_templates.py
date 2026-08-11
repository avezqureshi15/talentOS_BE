"""add template_version to email_templates

Revision ID: 0085
Revises: 0084
Create Date: 2026-08-10

"""
from alembic import op
import sqlalchemy as sa


revision = "0085"
down_revision = "0084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_templates",
        sa.Column("template_version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("email_templates", "template_version")
