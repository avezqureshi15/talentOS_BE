from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_locations(value: list[str]) -> list[str]:
    cleaned = [item.strip() for item in value if item and item.strip()]
    if not cleaned:
        raise ValueError("At least one location is required")
    for item in cleaned:
        if len(item) > 255:
            raise ValueError("Each location must be at most 255 characters")
    return cleaned


class HiringRequestCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    department: str = Field(..., min_length=1, max_length=255)
    location: list[str] = Field(..., min_length=1)
    type: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    requirements: list[str] | None = Field(None)
    benefits: list[str] | None = Field(None)
    is_active: bool = Field(False)
    custom_evaluation_criteria: str | None = Field(None)
    external_job_id: str | None = Field(None)
    rh_external_job_id: str | None = Field(None)
    tenant_id: int | None = Field(None, description="Superadmin-only override; otherwise derived from the caller's tenant")

    @field_validator("location")
    @classmethod
    def validate_location(cls, value: list[str]) -> list[str]:
        return _normalize_locations(value)


class HiringRequestUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    department: str | None = Field(None, min_length=1, max_length=255)
    location: list[str] | None = Field(None, min_length=1)
    type: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, min_length=1)
    requirements: list[str] | None = Field(None)
    benefits: list[str] | None = Field(None)
    is_active: bool | None = Field(None)
    custom_evaluation_criteria: str | None = Field(None)

    @field_validator("location")
    @classmethod
    def validate_location(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_locations(value)


class HiringRequestResponse(BaseModel):
    id: UUID
    tenant_id: int | None
    title: str
    department: str
    location: list[str]
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
