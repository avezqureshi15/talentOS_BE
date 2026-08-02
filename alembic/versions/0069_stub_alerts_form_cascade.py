"""stub: 0069 was applied on the deployed DB as the alerts.form_id cascade change

Revision ID: 0069
Revises: 0068
Create Date: 2026-08-02

NOTE: the deployed database was migrated under the revision id ``0069``
(the alerts.form_id ON DELETE CASCADE change, whose repo-level twin lives
at ``5d27bb707958`` between 0054 and 0055). That file was lost from this
history, so a no-op stub is provided to keep the chain linear:
0068 -> 0069 (no-op) -> 0070 (alerts -> notifications).
A fresh database already receives the cascade from ``5d27bb707958`` and
therefore needs nothing from this migration.
"""

from typing import ClassVar

revision: str = "0069"
down_revision: str | None = "0068"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
