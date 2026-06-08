from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class NotificationOut(BaseModel):
    id: UUID
    type: str
    title: str
    body: str
    entity_type: str
    entity_id: UUID
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
