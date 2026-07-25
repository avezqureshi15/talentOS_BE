from pydantic import BaseModel, Field


class GenerateReviewQuestionsRequest(BaseModel):
    """Request body for talentOS_AI POST /api/v1/evaluation/generate-review-questions."""

    transcription: str | None = None
    jd_details: str | None = None


class ReviewPhase(BaseModel):
    phase: str
    questions: list[str] = Field(default_factory=list)


class GenerateReviewQuestionsResponse(BaseModel):
    """Response body from the generate-review-questions endpoint."""

    phases: list[ReviewPhase] = Field(default_factory=list)


class ReviewQuestionsPayload(BaseModel):
    """Questions served to the REVIEW form (from interview or static fallback)."""

    questions_source: str
    phases: list[ReviewPhase] = Field(default_factory=list)
