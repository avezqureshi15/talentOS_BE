"""add_cascade_delete_on_candidate_relations

Revision ID: c9cefeb0e6c2
Revises: 0054
Create Date: 2026-07-29 08:31:10.070480
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9cefeb0e6c2'
down_revision: Union[str, None] = '0054'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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

    # --- CASCADE : events.candidate_id → candidates.id (new FK) ---
    op.create_foreign_key(
        "fk_events_candidate_id", "events", "candidates",
        ["candidate_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Remove events FK (added in this migration)
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
