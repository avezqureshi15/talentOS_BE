import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    # Append-only. No updates. No deletes. Ever.

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_actor", "actor_email"),
        Index("ix_audit_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # job_posting | candidate | user
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # JOB_CREATED | JOB_PUBLISHED | JOB_CLOSED
    # BENCH_CHECKED | JOB_FILLED_INTERNAL
    # CANDIDATE_EVALUATED | CANDIDATE_SHORTLISTED | CANDIDATE_REJECTED
    # SCORE_OVERRIDDEN | SHORTLIST_CONFIRMED | THRESHOLD_CHANGED
    # USER_ADDED | USER_REMOVED | USER_ROLE_CHANGED
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
