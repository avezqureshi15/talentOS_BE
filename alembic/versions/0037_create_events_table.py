"""create events table

Revision ID: 0037
Revises: 0036_add_round_verdict_to_rounds
Create Date: 2026-07-13 06:45:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("event_name", sa.String(100), nullable=False),
        sa.Column("state_code", sa.String(100), nullable=False),
        sa.Column("actor_type", sa.String(20), nullable=True),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("action_url", sa.Text(), nullable=True),
        sa.Column("action_label", sa.String(100), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index("idx_events_entity", "events", ["entity_type", "entity_id"])
    op.create_index("idx_events_job_id", "events", ["job_id"])
    op.create_index("idx_events_candidate_id", "events", ["candidate_id"])
    op.create_index("idx_events_state_code", "events", ["state_code"])
    op.create_index("idx_events_created_at", "events", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_events_created_at", table_name="events")
    op.drop_index("idx_events_state_code", table_name="events")
    op.drop_index("idx_events_candidate_id", table_name="events")
    op.drop_index("idx_events_job_id", table_name="events")
    op.drop_index("idx_events_entity", table_name="events")
    op.drop_table("events")
