import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RoundInterviewer(Base):
    __tablename__ = "round_interviewers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    round_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
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

    employee = relationship("Employee", lazy="joined")
    user = relationship(
        "User",
        primaryjoin="foreign(User.employee_id) == RoundInterviewer.employee_id",
        viewonly=True,
        uselist=False,
        lazy="joined",
    )
