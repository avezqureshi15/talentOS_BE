"""migrate hiring_requests.location to JSON list

Converts scalar location strings into JSON arrays so a job can have
multiple locations (Bug_010).

Revision ID: 0084
Revises: 0083
Create Date: 2026-08-11

"""
from typing import ClassVar

from alembic import op

revision: str = "0084"
down_revision: str | None = "0083"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE hiring_requests
        ALTER COLUMN location TYPE JSON
        USING CASE
            WHEN location IS NULL OR btrim(location::text) = '' THEN '[]'::json
            WHEN left(btrim(location::text), 1) = '[' THEN location::json
            ELSE json_build_array(location::text)
        END
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE hiring_requests
        ALTER COLUMN location TYPE VARCHAR(255)
        USING CASE
            WHEN jsonb_typeof(location::jsonb) = 'array'
                 AND jsonb_array_length(location::jsonb) > 0
            THEN left(location::jsonb->>0, 255)
            ELSE left(location::text, 255)
        END
        """
    )
