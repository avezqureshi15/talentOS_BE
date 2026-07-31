"""add round_type column to rounds table

Revision ID: 0062
Revises: 0061
Create Date: 2026-07-31

No-op migration: this file previously duplicated revision 0044 and its
DDL (rounds.round_type) is already applied to the database. Renumbered
to keep the alembic chain linear; upgrade/downgrade intentionally do nothing.

"""
from alembic import op
import sqlalchemy as sa


revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
