from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChatStreamRequest(BaseModel):
    message: str
    chat_id: str | None = None
    visitor_id: str | None = None


class ChatCreate(BaseModel):
    visitor_id: str
    title: str


class ChatResponse(BaseModel):
    id: UUID
    visitor_id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageCreate(BaseModel):
    chat_id: UUID
    role: str
    content: str


class MessageResponse(BaseModel):
    id: int
    chat_id: UUID
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
