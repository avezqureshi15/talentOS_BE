from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreate(BaseModel):
    job_id: UUID = Field(...)
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., max_length=255)
    phone: str = Field(..., max_length=50)
    cover_letter: str = Field(..., min_length=1)
    resume_url: str | None = Field(None, max_length=1024)


class JobListingBrief(BaseModel):
    title: str
    department: str
    location: str

    model_config = ConfigDict(from_attributes=True)


class ApplicationResponse(BaseModel):
    id: int
    job_id: UUID
    name: str
    email: str
    phone: str
    cover_letter: str
    resume_url: str | None
    status: str
    created_at: datetime
    job_listing: JobListingBrief | None = None

    model_config = ConfigDict(from_attributes=True)


class EvaluatedCandidate(BaseModel):
    id: str
    candidate_id: int
    job_id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    cover_letter: str | None = None
    resume_url: str | None = None
    current_ctc: str | None = None
    expected_ctc: str | None = None
    location: str | None = None
    years_of_experience: str | None = None
    notice_period: str | None = None
    how_did_you_hear: str | None = None
    linkedin_url: str | None = None
    willing_to_relocate: bool = False
    status: str | None = None
    fit_score: int | None = None
    summary_md: str | None = None
    evaluated_at: str | None = None
    scheduled: bool = False
    current_round_id: str | None = None
    final_verdict: str | None = None


class EvaluatedCandidatesResponse(BaseModel):
    data: list[EvaluatedCandidate]


class FinalVerdictUpdate(BaseModel):
    verdict: Literal["SELECTED", "REJECTED"]


class PaginatedEvaluatedCandidatesResponse(BaseModel):
    data: list[EvaluatedCandidate]
    total: int
    limit: int
    offset: int
