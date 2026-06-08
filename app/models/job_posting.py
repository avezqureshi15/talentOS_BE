import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Role identity
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    stream: Mapped[str] = mapped_column(String(100), nullable=False)
    band: Mapped[str] = mapped_column(String(50), nullable=False)
    designation: Mapped[str] = mapped_column(String(200), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(50), nullable=False, default="full_time")
    # full_time | internship

    # Requirements
    experience_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skills_required: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    # [{skill: str, priority: required|preferred}]
    urgency: Mapped[str] = mapped_column(String(50), nullable=False, default="standard")
    # standard | priority | critical

    # JD
    jd_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jd_raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # ATS
    ats_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=70)

    # Status
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    # draft | bench_check | active | filled_internal | filled_external | closed

    # Bench check
    bench_check_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bench_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Careers page reference
    careers_page_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Stats (denormalised for fast dashboard queries)
    total_applications: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_shortlisted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Ownership
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)

    # Timestamps
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
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
