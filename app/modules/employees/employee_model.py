from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    emp_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    personal_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hrms_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    delivery_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    work_location_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    doj: Mapped[date | None] = mapped_column(Date, nullable=True)
    doe: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    internship_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    band: Mapped[str | None] = mapped_column(String(50), nullable=True)
    skills: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
