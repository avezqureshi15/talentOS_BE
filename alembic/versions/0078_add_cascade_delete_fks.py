"""re-apply cascade deletes already covered by earlier (skipped) migrations

c9cefeb0e6c2 / 5d27bb707958 added ON DELETE CASCADE (and SET NULL for
candidates.current_round_id) but sit at revision ``0054`` in the history.
Databases stamped at or above ``0072`` were created before those landed, so
``alembic upgrade head`` treats them as already applied and never runs them.

This revision moves the same DDL to the head so every environment converges
to the same final FK behavior regardless of when it was first stamped.

FK definition source: the SQLAlchemy models (declared online delete=CASCADE /
SET NULL) and c9cefeb0e6c2.

Revision ID: 0078
Revises: 0077
Create Date: 2026-08-05

"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0078"
down_revision: str | None = "0077"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def _has_fk(table: str, constraint: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(fk["name"] == constraint for fk in inspector.get_foreign_keys(table))


def upgrade() -> None:
    # --- CASCADE : rounds.candidate_id → candidates.id ---
    op.drop_constraint("rounds_candidate_id_fkey", "rounds", type_="foreignkey")
    op.create_foreign_key(
        "rounds_candidate_id_fkey", "rounds", "candidates",
        ["candidate_id"], ["id"],
        ondelete="CASCADE",
    )

    # --- CASCADE : forms.candidate_id → candidates.id ---
    op.drop_constraint("fk_forms_candidate_id", "forms", type_="foreignkey")
    op.create_foreign_key(
        "fk_forms_candidate_id", "forms", "candidates",
        ["candidate_id"], ["id"],
        ondelete="CASCADE",
    )

    # --- CASCADE : forms.round_id → rounds.id ---
    op.drop_constraint("fk_forms_round_id", "forms", type_="foreignkey")
    op.create_foreign_key(
        "fk_forms_round_id", "forms", "rounds",
        ["round_id"], ["id"],
        ondelete="CASCADE",
    )

    # --- CASCADE : reviews.round_id → rounds.id ---
    op.drop_constraint("reviews_round_id_fkey", "reviews", type_="foreignkey")
    op.create_foreign_key(
        "reviews_round_id_fkey", "reviews", "rounds",
        ["round_id"], ["id"],
        ondelete="CASCADE",
    )

    # --- CASCADE : interviews.round_id → rounds.id ---
    op.drop_constraint("interviews_round_id_fkey", "interviews", type_="foreignkey")
    op.create_foreign_key(
        "interviews_round_id_fkey", "interviews", "rounds",
        ["round_id"], ["id"],
        ondelete="CASCADE",
    )

    # --- CASCADE : round_interviewers.round_id → rounds.id ---
    op.drop_constraint("round_interviewers_round_id_fkey", "round_interviewers", type_="foreignkey")
    op.create_foreign_key(
        "round_interviewers_round_id_fkey", "round_interviewers", "rounds",
        ["round_id"], ["id"],
        ondelete="CASCADE",
    )

    # --- SET NULL : candidates.current_round_id → rounds.id ---
    op.drop_constraint("fk_candidates_current_round", "candidates", type_="foreignkey")
    op.create_foreign_key(
        "fk_candidates_current_round", "candidates", "rounds",
        ["current_round_id"], ["id"],
        ondelete="SET NULL",
    )

    # --- CASCADE : events.candidate_id → candidates.id (added by c9cefeb0e6c2
    # on fresh DBs, still missing on DBs stamped at/above 0072) ---
    if not _has_fk("events", "fk_events_candidate_id"):
        op.create_foreign_key(
            "fk_events_candidate_id", "events", "candidates",
            ["candidate_id"], ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    if _has_fk("events", "fk_events_candidate_id"):
        op.drop_constraint("fk_events_candidate_id", "events", type_="foreignkey")

    # Revert candidates.current_round_id → rounds.id (remove SET NULL)
    op.drop_constraint("fk_candidates_current_round", "candidates", type_="foreignkey")
    op.create_foreign_key(
        "fk_candidates_current_round", "candidates", "rounds",
        ["current_round_id"], ["id"],
    )

    # Revert round_interviewers.round_id → rounds.id (remove CASCADE)
    op.drop_constraint("round_interviewers_round_id_fkey", "round_interviewers", type_="foreignkey")
    op.create_foreign_key(
        "round_interviewers_round_id_fkey", "round_interviewers", "rounds",
        ["round_id"], ["id"],
    )

    # Revert interviews.round_id → rounds.id (remove CASCADE)
    op.drop_constraint("interviews_round_id_fkey", "interviews", type_="foreignkey")
    op.create_foreign_key(
        "interviews_round_id_fkey", "interviews", "rounds",
        ["round_id"], ["id"],
    )

    # Revert reviews.round_id → rounds.id (remove CASCADE)
    op.drop_constraint("reviews_round_id_fkey", "reviews", type_="foreignkey")
    op.create_foreign_key(
        "reviews_round_id_fkey", "reviews", "rounds",
        ["round_id"], ["id"],
    )

    # Revert forms.round_id → rounds.id (remove CASCADE)
    op.drop_constraint("fk_forms_round_id", "forms", type_="foreignkey")
    op.create_foreign_key(
        "fk_forms_round_id", "forms", "rounds",
        ["round_id"], ["id"],
    )

    # Revert forms.candidate_id → candidates.id (remove CASCADE)
    op.drop_constraint("fk_forms_candidate_id", "forms", type_="foreignkey")
    op.create_foreign_key(
        "fk_forms_candidate_id", "forms", "candidates",
        ["candidate_id"], ["id"],
    )

    # Revert rounds.candidate_id → candidates.id (remove CASCADE)
    op.drop_constraint("rounds_candidate_id_fkey", "rounds", type_="foreignkey")
    op.create_foreign_key(
        "rounds_candidate_id_fkey", "rounds", "candidates",
        ["candidate_id"], ["id"],
    )