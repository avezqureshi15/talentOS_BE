"""add email_templates table

Revision ID: 0084
Revises: 0083
Create Date: 2026-08-10

"""
from alembic import op
import sqlalchemy as sa


revision = "0084"
down_revision = "0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_templates",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("subject_template", sa.Text(), nullable=False),
        sa.Column("body_html_template", sa.Text(), nullable=False),
        sa.Column("is_editable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(150), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("email_templates")
