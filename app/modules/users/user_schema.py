from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    id: int
    emp_id: str
    email: str
    personal_email: str | None
    name: str
    status: str
    user_type: str
    designation: str
    department: str
    phone_number: str | None
    role: str
    work_mode: str
    delivery_status: str
    work_location_type: str
    doj: date
    doe: date | None
    date_of_birth: date
    internship_duration: int | None
    band: str
    skills: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedUserResponse(BaseModel):
    data: list[UserResponse]
    total: int
    page: int
    per_page: int
    has_more: bool
