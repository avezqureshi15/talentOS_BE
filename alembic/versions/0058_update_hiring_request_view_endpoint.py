"""update hiring_request.view endpoint to include detail endpoint

Revision ID: 0058
Revises: 0057
Create Date: 2026-07-30

"""
from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE permissions SET endpoint = :endpoint WHERE code = :code"
        ).bindparams(
            endpoint="GET /api/v1/hiring-requests, GET /api/v1/hiring-requests/{id}",
            code="hiring_request.view",
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE permissions SET endpoint = :endpoint WHERE code = :code"
        ).bindparams(
            endpoint="GET /api/v1/hiring-requests",
            code="hiring_request.view",
        )
    )
