"""Add external interviewer support (manually-entered email, no employee record)

Lets a scheduler type an interviewer's email directly instead of picking an
employee from the org: rounds carry the email/name when there's no
round_interviewers row to point at, and slots.employee_id becomes nullable
so an ad-hoc time window (not tied to anyone's calendar) can be created for
that booking.

Revision ID: 0099
Revises: 0098
Create Date: 2026-09-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0099"
down_revision: Union[str, None] = "0098"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rounds", sa.Column("external_interviewer_email", sa.String(length=255), nullable=True))
    op.add_column("rounds", sa.Column("external_interviewer_name", sa.String(length=255), nullable=True))
    op.alter_column("slots", "employee_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("slots", "employee_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("rounds", "external_interviewer_name")
    op.drop_column("rounds", "external_interviewer_email")
