"""add round_id and candidate_id to forms

Revision ID: 0032
Revises: 0031
Create Date: 2026-07-12

"""

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.add_column("forms", sa.Column("round_id", sa.Uuid(), nullable=True))
    op.add_column("forms", sa.Column("candidate_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_forms_round_id", "forms", "rounds", ["round_id"], ["id"])
    op.create_foreign_key("fk_forms_candidate_id", "forms", "candidates", ["candidate_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_forms_candidate_id", "forms", type_="foreignkey")
    op.drop_constraint("fk_forms_round_id", "forms", type_="foreignkey")
    op.drop_column("forms", "candidate_id")
    op.drop_column("forms", "round_id")
