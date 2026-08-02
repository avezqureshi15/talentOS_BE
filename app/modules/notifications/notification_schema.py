from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: UUID
    employee_id: int
    type: str
    title: str
    body: str | None = None
    action_url: str | None = None
    action_label: str | None = None
    form_id: UUID | None = None
    job_id: UUID | None = None
    candidate_id: int | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationPagination(BaseModel):
    current_page: int
    per_page: int
    total_records: int
    has_more: bool


class NotificationsData(BaseModel):
    notifications: list[NotificationResponse]
    pagination: NotificationPagination


class NotificationListResponse(BaseModel):
    success: bool = True
    data: NotificationsData


class UnreadCountData(BaseModel):
    unread_count: int


class UnreadCountResponse(BaseModel):
    success: bool = True
    data: UnreadCountData
