from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmailTemplate(Base):
    """An editable email template.

    ``id`` is a stable slug (e.g. ``slot_form``) used across the app as the
    template key. ``subject_template`` and ``body_html_template`` may contain
    ``{placeholder}`` tokens that are formatted with real values at send time.
    """

    __tablename__ = "email_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    subject_template: Mapped[str] = mapped_column(Text, nullable=False)
    body_html_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_editable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    template_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
