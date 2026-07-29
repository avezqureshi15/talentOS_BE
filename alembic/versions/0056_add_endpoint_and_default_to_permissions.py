"""add endpoint and is_default columns to permissions

Revision ID: 0056
Revises: 0055
Create Date: 2026-07-29

"""
from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None

PERMISSION_ENDPOINTS: dict[str, str] = {
    "application.view": "GET /api/v1/applications",
    "application.evaluate": "POST /api/v1/evaluations/evaluate-async",
    "application.reject": "POST /api/v1/rounds/{round_id}/reject",
    "hiring_request.create": "POST /api/v1/hiring-requests",
    "hiring_request.edit": "PUT /api/v1/hiring-requests/{id}",
    "hiring_request.view": "GET /api/v1/hiring-requests",
    "hiring_request.delete": "DELETE /api/v1/hiring-requests/{id}",
    "user.invite": "POST /api/v1/admin/users/invites",
    "user.manage": "PATCH /api/v1/admin/users/{user_id}",
    "tenant.view": "GET /api/v1/superadmin/tenants",
    "tenant.edit": "PATCH /api/v1/superadmin/tenants/{tenant_id}",
    "settings.view": "GET /api/v1/settings",
    "settings.edit": "PATCH /api/v1/settings",
    "slot.submit": "POST /api/v1/slots",
    "slot.view_all": "GET /api/v1/slots/employee",
    "review.submit": "POST /api/v1/reviews",
    "review.view_all": "GET /api/v1/reviews/round/{round_id}",
    "chat": "GET /api/v1/chat/chats",
}

DEFAULT_PERMISSIONS: list[str] = [
    "application.view",
    "hiring_request.view",
    "settings.view",
    "slot.submit",
    "slot.view_all",
    "review.submit",
    "review.view_all",
    "chat",
]


def upgrade() -> None:
    op.add_column("permissions", sa.Column("endpoint", sa.String(255), nullable=False, server_default=""))
    op.add_column("permissions", sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")))

    for code, endpoint in PERMISSION_ENDPOINTS.items():
        op.execute(
            sa.text("UPDATE permissions SET endpoint = :endpoint WHERE code = :code").bindparams(
                endpoint=endpoint, code=code
            )
        )

    for code in DEFAULT_PERMISSIONS:
        op.execute(
            sa.text("UPDATE permissions SET is_default = true WHERE code = :code").bindparams(code=code)
        )


def downgrade() -> None:
    op.drop_column("permissions", "is_default")
    op.drop_column("permissions", "endpoint")
