"""backfill api_key_permissions for legacy keys with zero rows

Historically, `ApiKeyService.get_permissions_for_key` fell back to granting
ALL permissions when a key had no rows in `api_key_permissions`. That
fallback has been removed; without a backfill, any legacy key that was
created before permission rows were seeded would silently lose access.

This migration finds every active api_keys row that has zero permission
grants and inserts one row per default permission (`permissions.is_default
= true`). Keys already carrying explicit grants are left untouched.

Revision ID: 0079
Revises: 0078
Create Date: 2026-08-05
"""
from typing import ClassVar

from alembic import op

revision: str = "0079"
down_revision: str | None = "0078"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO api_key_permissions (api_key_id, permission_code)
        SELECT k.id, p.code
        FROM api_keys k
        CROSS JOIN permissions p
        WHERE p.is_default = true
          AND NOT EXISTS (
              SELECT 1 FROM api_key_permissions akp WHERE akp.api_key_id = k.id
          )
        ON CONFLICT (api_key_id, permission_code) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Data backfill — no downgrade. The inserted rows are indistinguishable
    # from grants made through the normal API surface.
    pass
