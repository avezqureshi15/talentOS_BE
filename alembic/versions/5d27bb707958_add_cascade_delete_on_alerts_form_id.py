"""add_cascade_delete_on_alerts_form_id

Revision ID: 5d27bb707958
Revises: c9cefeb0e6c2
Create Date: 2026-07-29 08:43:41.924812
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5d27bb707958'
down_revision: Union[str, None] = 'c9cefeb0e6c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("fk_alerts_form_id", "alerts", type_="foreignkey")
    op.create_foreign_key(
        "fk_alerts_form_id", "alerts", "forms",
        ["form_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_alerts_form_id", "alerts", type_="foreignkey")
    op.create_foreign_key(
        "fk_alerts_form_id", "alerts", "forms",
        ["form_id"], ["id"],
    )
