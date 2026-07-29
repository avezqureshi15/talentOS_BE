import uuid
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict


class RoundVerdictRequest(BaseModel):
    verdict: Literal["shortlisted", "rejected"]
    remark: str = ""


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
    round_type: str | None = None
    candidate_id: int | None = None
    slot_id: uuid.UUID | None = None
    jd_id: uuid.UUID | None = None
    scheduled_date: str | None = None
    scheduled_time: str | None = None
    scheduled_end_date: str | None = None
    scheduled_end_time: str | None = None


class RoundResponse(BaseModel):
    id: uuid.UUID
    candidate_id: int | None = None
    slot_id: uuid.UUID | None = None
    jd_id: uuid.UUID | None = None
    name: str | None = None
    round_type: str | None = None
    round_verdict: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoundDetailResponse(BaseModel):
    id: uuid.UUID
    round_type: str | None = None
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


class RoundListItem(BaseModel):
    id: str
    name: str | None = None
    round_verdict: str | None = None
    candidate_name: str | None = None
    candidate_id: str | None = None
    position_title: str | None = None
    created_at: str | None = None


class PaginatedRoundResponse(BaseModel):
    items: list[RoundListItem]
    total: int
    page: int
    per_page: int
    has_more: bool
