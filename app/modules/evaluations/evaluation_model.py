from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvaluationStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SHORTLISTED = "SHORTLISTED"
    REJECTED = "REJECTED"
    INVALID = "INVALID"
    FAILED = "FAILED"


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Dedup / idempotency key — the Supabase job_applications.id.
    # Stored as string to stay agnostic to Supabase's id type (int/uuid).
    application_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    job_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

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

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=EvaluationStatus.QUEUED.value, index=True
    )

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
