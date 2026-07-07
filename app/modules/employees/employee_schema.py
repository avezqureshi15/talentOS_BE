from datetime import datetime

from pydantic import BaseModel


class EmployeeFormStatusItem(BaseModel):
    emp_id: str
    name: str
    email: str
    type: str
    status: str
    last_sent_at: datetime
    updated_at: datetime


class PaginatedEmployeeFormStatusResponse(BaseModel):
    data: list[EmployeeFormStatusItem]
    total: int
    page: int
    per_page: int
    has_more: bool
