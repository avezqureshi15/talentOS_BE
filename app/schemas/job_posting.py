from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class SkillItem(BaseModel):
    skill: str
    priority: str = "required"  # required | preferred


class JobPostingCreate(BaseModel):
    title: str
    stream: str
    band: str
    designation: str
    employment_type: str = "full_time"
    experience_min: int = 0
    skills_required: List[SkillItem] = []
    urgency: str = "standard"
    jd_text: Optional[str] = None
    jd_raw: Optional[dict] = None
    ats_threshold: int = 70


class JobPostingUpdate(BaseModel):
    title: Optional[str] = None
    jd_text: Optional[str] = None
    jd_raw: Optional[dict] = None
    skills_required: Optional[List[SkillItem]] = None
    experience_min: Optional[int] = None
    urgency: Optional[str] = None
    ats_threshold: Optional[int] = None


class JobPostingOut(BaseModel):
    id: UUID
    title: str
    stream: str
    band: str
    designation: str
    employment_type: str
    experience_min: int
    skills_required: list
    urgency: str
    jd_text: Optional[str]
    ats_threshold: int
    status: str
    bench_check_done: bool
    total_applications: int
    total_shortlisted: int
    created_by: str
    published_at: Optional[datetime]
    closed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ThresholdUpdateIn(BaseModel):
    ats_threshold: int
