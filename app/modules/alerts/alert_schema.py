from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertResponse(BaseModel):
    id: UUID
    emp_id: str
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
