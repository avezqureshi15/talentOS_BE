from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertResponse(BaseModel):
    id: UUID
    employee_id: int
    form_id: UUID | None = None
    type: str
    is_read: bool
    created_at: datetime
    updated_at: datetime
    name: str = ""
    email: str = ""
    phone_number: str = ""
    form_link: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedAlertResponse(BaseModel):
    data: list[AlertResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


# ── Enriched list response ──────────────────────────────────

class EmployeeBrief(BaseModel):
    id: str
    name: str
    email: str
    phone: str


class InterviewBrief(BaseModel):
    id: str
    candidate_name: str
    position: str


class AlertListItem(BaseModel):
    id: str
    type: str
    employee: EmployeeBrief
    slot_link: str | None = None
    review_link: str | None = None
    interview: InterviewBrief | None = None
    created_at: str | None = None


class AlertPagination(BaseModel):
    current_page: int
    per_page: int
    total_records: int
    has_more: bool


class AlertsData(BaseModel):
    alerts: list[AlertListItem]
    pagination: AlertPagination


class AlertListResponse(BaseModel):
    success: bool = True
    data: AlertsData
