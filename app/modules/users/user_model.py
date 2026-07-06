from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    emp_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    personal_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    user_type: Mapped[str] = mapped_column(String(50), nullable=False)
    designation: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    work_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(50), nullable=False)
    work_location_type: Mapped[str] = mapped_column(String(50), nullable=False)
    doj: Mapped[date] = mapped_column(Date, nullable=False)
    doe: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    internship_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    band: Mapped[str] = mapped_column(String(50), nullable=False)
    skills: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
