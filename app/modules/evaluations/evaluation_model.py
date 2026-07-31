import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import EvaluationStatus
from app.db.base import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Dedup / idempotency key — the Supabase job_applications.id.
    # Stored as string to stay agnostic to Supabase's id type (int/uuid).
    external_application_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    external_job_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    current_ctc: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expected_ctc: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    years_of_experience: Mapped[str | None] = mapped_column(String(10), nullable=True)
    notice_period: Mapped[str | None] = mapped_column(String(50), nullable=True)
    how_did_you_hear: Mapped[str | None] = mapped_column(String(100), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    scheduled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    willing_to_relocate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    candidate_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="REGULAR"
    )

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=EvaluationStatus.QUEUED.value, index=True
    )

    stage: Mapped[str | None] = mapped_column(String(50), nullable=True)

    fit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    ats_threshold_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    current_round_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("rounds.id", ondelete="SET NULL"), nullable=True)
    rh_external_candidate_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rh_external_screening_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    final_verdict: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reviews: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    review_verdict: Mapped[str | None] = mapped_column(String(50), nullable=True)
