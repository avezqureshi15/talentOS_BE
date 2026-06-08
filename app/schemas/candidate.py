from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class ScoreBreakdown(BaseModel):
    skills_match: float
    exp_match: float
    qual_match: float


class CandidateOut(BaseModel):
    id: UUID
    job_posting_id: UUID
    name: str
    email: str
    phone: str
    resume_url: str
    fit_score: Optional[float]
    score_breakdown: Optional[dict]
    score_explanation: Optional[str]
    source: str
    referral_by: Optional[str]
    status: str
    is_shortlisted: bool
    shortlisted_by: Optional[str]
    shortlisted_at: Optional[datetime]
    hr_override: bool
    hr_override_score: Optional[float]
    hr_override_reason: Optional[str]
    hr_override_by: Optional[str]
    applied_at: datetime
    evaluated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ScoreOverrideIn(BaseModel):
    new_score: float
    reason: str


class ShortlistConfirmOut(BaseModel):
    job_posting_id: UUID
    total_confirmed: int
    status: str = "screening_queued"
