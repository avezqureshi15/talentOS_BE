"""Merge 0070 and 0071 heads

Revision ID: 0072
Revises: 0070, 0071
Create Date: 2026-08-04
"""

from typing import ClassVar

from alembic import op

revision: str = "0072"
down_revision: ClassVar[tuple[str, str] | None] = ("0070", "0071")
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
