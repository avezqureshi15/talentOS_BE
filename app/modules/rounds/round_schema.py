import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RatingItem(BaseModel):
    label: str
    score: float
    max_score: float
    entity_type: str | None = None


class ReviewEntity(BaseModel):
    entity_type: str
    verdict: str | None = None
    ratings: list[RatingItem] = []

    model_config = ConfigDict(extra="allow")


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
    round_verdict: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoundDetailResponse(BaseModel):
    id: uuid.UUID
    round: str | None = None
    duration: str | None = None
    interview_type: str | None = None
    occurred_on: str | None = None
    slot: str | None = None
    status: str | None = None
    candidate: str | None = None
    role: str | None = None
    jd_label: str | None = None
    interviewer: str | None = None
    reviews: list[ReviewEntity] = []
