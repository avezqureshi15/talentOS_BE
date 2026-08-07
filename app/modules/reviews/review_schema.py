import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ReviewAnswerItem(BaseModel):
    question: str = Field(..., min_length=1)
    score: int = Field(..., ge=1, le=5)
    notes: str | None = None


class ReviewAnswerPhase(BaseModel):
    phase: str = Field(..., min_length=1)
    answers: list[ReviewAnswerItem] = Field(..., min_length=1)


class ReviewAnswerSectionItem(BaseModel):
    question: str = Field(..., min_length=1)
    score: int = Field(..., ge=1, le=5)
    notes: str | None = None


class ReviewAnswerSection(BaseModel):
    section: str = Field(..., min_length=1)
    answers: list[ReviewAnswerSectionItem] = Field(..., min_length=1)


class InterviewerReviewsPayload(BaseModel):
    """Interviewer review snapshot stored in reviews.reviews JSONB."""

    questions_source: str = Field(..., min_length=1)
    phases: list[ReviewAnswerPhase] | None = None       # legacy: transcript-based
    sections: list[ReviewAnswerSection] | None = None   # new: design review sections
    average_rating: float | None = None
    skills: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_phases_or_sections(self) -> "InterviewerReviewsPayload":
        if not self.phases and not self.sections:
            raise ValueError("Either phases or sections must be provided")
        return self
