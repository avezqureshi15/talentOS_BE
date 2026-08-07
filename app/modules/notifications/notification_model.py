import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid as SA_Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationType(str, Enum):
    SLOTS = "SLOTS"
    REVIEW = "REVIEW"
    REVIEW_SUBMITTED = "REVIEW_SUBMITTED"
    JOB_ASSIGNED = "JOB_ASSIGNED"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    AI_SCREENING_FLAGGED = "AI_SCREENING_FLAGGED"
    INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED"
    FINAL_VERDICT = "FINAL_VERDICT"
    JOB_CREATED = "JOB_CREATED"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(SA_Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    form_id: Mapped[uuid.UUID | None] = mapped_column(SA_Uuid(as_uuid=True), ForeignKey("forms.id", ondelete="CASCADE"), nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(SA_Uuid(as_uuid=True), nullable=True)
    candidate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False, default=NotificationType.SLOTS.value)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    action_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    action_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
