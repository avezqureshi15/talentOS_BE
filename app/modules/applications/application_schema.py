from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreate(BaseModel):
    job_id: int = Field(...)
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
    job_id: int
    name: str
    email: str
    phone: str
    cover_letter: str
    resume_url: str | None
    status: str
    created_at: datetime
    job_listing: JobListingBrief | None = None

    model_config = ConfigDict(from_attributes=True)
