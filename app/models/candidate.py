import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, Text, JSON, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Personal info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)

    # Resume (URL only — file lives in Supabase Storage on careers page)
    resume_url: Mapped[str] = mapped_column(String(1000), nullable=False)

    # Evaluation results
    fit_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    score_breakdown: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # {skills_match: float, exp_match: float, qual_match: float}
    score_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source tracking
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="organic")
    # organic | referral
    referral_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Pipeline status
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="evaluating")
    # evaluating | shortlisted | rejected | screening_queued

    # Shortlist tracking
    is_shortlisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shortlisted_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # email or 'system'
    shortlisted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # HR override
    hr_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hr_override_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    hr_override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hr_override_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
