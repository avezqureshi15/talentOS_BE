from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class ChatMessageIn(BaseModel):
    message: str
    job_posting_id: Optional[UUID] = None
    session_id: Optional[UUID] = None


class ChatMessageOut(BaseModel):
    session_id: UUID
    job_posting_id: Optional[UUID]
    response: str
    tool_used: Optional[str] = None
