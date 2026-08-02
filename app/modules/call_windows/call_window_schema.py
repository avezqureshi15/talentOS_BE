import uuid
from datetime import time
from typing import Literal

from pydantic import BaseModel, Field


class CallWindowUpdate(BaseModel):
    screening_call_from: time | None = None
    screening_call_to: time | None = None
    screening_timezone: str | None = None


class CallWindowResponse(BaseModel):
    hiring_request_id: uuid.UUID
    screening_call_from: time | None = None
    screening_call_to: time | None = None
    screening_timezone: str = "Asia/Kolkata"
    sync_status: Literal["synced", "draft"] = "synced"
    sync_errors: list[str] = Field(default_factory=list)
