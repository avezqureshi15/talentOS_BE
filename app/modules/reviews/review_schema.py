import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewCreate(BaseModel):
    round_id: uuid.UUID
    entity_type: str
    reviews: dict | None = None
    verdict: str | None = None


class ReviewResponse(BaseModel):
    id: uuid.UUID
    round_id: uuid.UUID
    entity_type: str
    reviews: dict | None = None
    verdict: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewUpdate(BaseModel):
    reviews: dict | None = None
    verdict: str | None = None


class ReviewUpdateByRound(BaseModel):
    entity_type: str
    reviews: dict
    verdict: str | None = None
