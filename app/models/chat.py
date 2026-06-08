import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    hr_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    job_posting_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("job_postings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    messages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # [{role: user|assistant, content: str, tool_calls: [], timestamp: str}]
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
