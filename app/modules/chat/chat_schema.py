from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChatStreamRequest(BaseModel):
    message: str
    chat_id: str | None = None


class ChatResponse(BaseModel):
    id: UUID
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    id: int
    chat_id: UUID
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
