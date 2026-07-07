import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

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

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emp_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(10), nullable=False, default=FormType.SLOTS.value)
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
