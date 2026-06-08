import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class BandDesignation(Base):
    __tablename__ = "band_designations"

    __table_args__ = (
        UniqueConstraint("stream", "band", "designation", name="uq_stream_band_designation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    stream: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    band: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    designation: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
