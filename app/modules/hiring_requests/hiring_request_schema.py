from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HiringRequestCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    department: str = Field(..., min_length=1, max_length=255)
    location: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    requirements: list[str] | None = Field(None)
    benefits: list[str] | None = Field(None)
    is_active: bool = Field(False)
    custom_evaluation_criteria: str | None = Field(None)
    external_job_id: str | None = Field(None)
    rh_external_job_id: str | None = Field(None)


class HiringRequestUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    department: str | None = Field(None, min_length=1, max_length=255)
    location: str | None = Field(None, min_length=1, max_length=255)
    type: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, min_length=1)
    requirements: list[str] | None = Field(None)
    benefits: list[str] | None = Field(None)
    is_active: bool | None = Field(None)
    custom_evaluation_criteria: str | None = Field(None)


class HiringRequestResponse(BaseModel):
    id: UUID
    title: str
    department: str
    location: str
    type: str
    description: str
    requirements: list[str] | None
    benefits: list[str] | None
    is_active: bool
    custom_evaluation_criteria: str | None
    external_job_id: UUID | None
    rh_external_job_id: str | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
