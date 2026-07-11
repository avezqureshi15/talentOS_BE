import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RoundCreate(BaseModel):
    name: str | None = None
    candidate_id: int | None = None
    slot_id: uuid.UUID | None = None
    jd_id: uuid.UUID | None = None


class RoundResponse(BaseModel):
    id: uuid.UUID
    candidate_id: int | None = None
    slot_id: uuid.UUID | None = None
    jd_id: uuid.UUID | None = None
    name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
