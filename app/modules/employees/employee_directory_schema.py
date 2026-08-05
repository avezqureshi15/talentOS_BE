from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class EmployeeResponse(BaseModel):
    id: int
    user_id: int | None = None
    emp_id: str
    email: str
    personal_email: str | None = None
    name: str
    contact_number: str | None = None
    hrms_id: str | None = None
    status: str | None = None
    user_type: str | None = None
    designation: str | None = None
    department: str | None = None
    work_mode: str | None = None
    delivery_status: str | None = None
    work_location_type: str | None = None
    doj: date | None = None
    doe: date | None = None
    date_of_birth: date | None = None
    internship_duration: int | None = None
    band: str | None = None
    skills: str | None = None
    tenant_id: int | None = None
    created_at: datetime
    slots_count: int = 0
    has_slots: bool = False

    model_config = ConfigDict(from_attributes=True)


class PaginatedEmployeeResponse(BaseModel):
    data: list[EmployeeResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


class CreateEmployeeRequest(BaseModel):
    emp_id: str
    email: str
    name: str
    contact_number: str | None = None
    hrms_id: str | None = None
    personal_email: str | None = None
    designation: str | None = None
    department: str | None = None
    work_mode: str | None = None
    work_location_type: str | None = None
    doj: date | None = None
    date_of_birth: date | None = None
    band: str | None = None
    skills: str | None = None
    status: str | None = "active"
    user_type: str | None = "employee"


class UpdateEmployeeRequest(BaseModel):
    email: str | None = None
    name: str | None = None
    contact_number: str | None = None
    hrms_id: str | None = None
    personal_email: str | None = None
    designation: str | None = None
    department: str | None = None
    work_mode: str | None = None
    delivery_status: str | None = None
    work_location_type: str | None = None
    doj: date | None = None
    doe: date | None = None
    date_of_birth: date | None = None
    internship_duration: int | None = None
    band: str | None = None
    skills: str | None = None
    status: str | None = None
    user_type: str | None = None
