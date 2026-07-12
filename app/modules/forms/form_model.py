import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid as SA_Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FormType(str, Enum):
    SLOTS = "SLOTS"
    REVIEW = "REVIEW"


class FormStatus(str, Enum):
    SENT = "SENT"
    SUBMITTED = "SUBMITTED"
    EXPIRED = "EXPIRED"


class Form(Base):
    __tablename__ = "forms"

    id: Mapped[uuid.UUID] = mapped_column(SA_Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(10), nullable=False, default=FormType.SLOTS.value)
    round_id: Mapped[uuid.UUID | None] = mapped_column(SA_Uuid(as_uuid=True), ForeignKey("rounds.id"), nullable=True)
    candidate_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("candidates.id"), nullable=True)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default=FormStatus.SENT.value
    )
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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

    employee: Mapped["User"] = relationship("User", lazy="joined")
