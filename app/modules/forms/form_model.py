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
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(10), nullable=False, default=FormType.SLOTS.value)
    round_id: Mapped[uuid.UUID | None] = mapped_column(SA_Uuid(as_uuid=True), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=True)
    candidate_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=True)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default=FormStatus.SENT.value
    )
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
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

    # Directory-side view — Employee is the HR truth for this form's owner.
    employee = relationship("Employee", lazy="joined")

    # Auth-scoped view — resolves through users.employee_id back-pointer for
    # callers that need a users.id (mail tasks, notifications).
    user = relationship(
        "User",
        primaryjoin="foreign(User.employee_id) == Form.employee_id",
        viewonly=True,
        uselist=False,
        lazy="joined",
    )
