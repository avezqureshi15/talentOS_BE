"""Add current_round_id and round_verdict to candidates

- candidates: add current_round_id (UUID, FK -> rounds.id) and round_verdict (String(50))

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("current_round_id", sa.Uuid(as_uuid=True), nullable=True))
    op.add_column("candidates", sa.Column("round_verdict", sa.String(length=50), nullable=True))
    op.create_foreign_key("fk_candidates_current_round", "candidates", "rounds", ["current_round_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_candidates_current_round", "candidates", type_="foreignkey")
    op.drop_column("candidates", "round_verdict")
    op.drop_column("candidates", "current_round_id")
