import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InterviewDesign(Base):
    __tablename__ = "interview_designs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hiring_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("hiring_requests.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    screening_sections: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    interview_sections: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    review_sections: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    # True once a kind has real, ready-to-use content — the FE uses these to
    # auto-fill a kind exactly once (on first arrival) and never again, so a
    # later manual edit is never silently overwritten by a re-generation.
    # screening starts seeded from a static template (see
    # _build_default_screening_sections), which does NOT count as generated —
    # interview seeded from an already-linked ai-recruitment-poc job DOES
    # count as generated (that existing content takes priority over an
    # auto-fill call). See get_or_seed_design / generate_design.
    screening_ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interview_ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
