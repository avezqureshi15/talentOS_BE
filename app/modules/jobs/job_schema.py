from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    department: str = Field(..., min_length=1, max_length=255)
    location: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    requirements: list[str] | None = Field(None)
    benefits: list[str] | None = Field(None)
    is_active: bool = Field(False)


class JobUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    department: str | None = Field(None, min_length=1, max_length=255)
    location: str | None = Field(None, min_length=1, max_length=255)
    type: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, min_length=1)
    requirements: list[str] | None = Field(None)
    benefits: list[str] | None = Field(None)
    is_active: bool | None = Field(None)


class JobResponse(BaseModel):
    id: UUID
    title: str
    department: str
    location: str
    type: str
    description: str
    requirements: list[str] | None
    benefits: list[str] | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
