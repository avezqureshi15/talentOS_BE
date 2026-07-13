import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid as SA_Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AlertType(str, Enum):
    SLOTS = "SLOTS"
    REVIEW = "REVIEW"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(SA_Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    form_id: Mapped[uuid.UUID | None] = mapped_column(SA_Uuid(as_uuid=True), ForeignKey("forms.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(10), nullable=False, default=AlertType.SLOTS.value)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
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
