import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SlotStatus(str, Enum):
    AVAILABLE = "available"
    BOOKED = "booked"
    INACTIVE = "inactive"


class Slot(Base):
    __tablename__ = "slots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SlotStatus.AVAILABLE.value
    )
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

    # Auth-scoped view of the slot's owner: resolves through the
    # users.employee_id back-pointer so callers that still need a users.id
    # (notifications, mail tasks) can use slot.user.id.
    user = relationship(
        "User",
        primaryjoin="foreign(User.employee_id) == Slot.employee_id",
        viewonly=True,
        uselist=False,
        lazy="joined",
    )
