from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class UserResponse(BaseModel):
    id: int
    emp_id: str
    email: str
    name: str
    status: str
    role: str
    created_at: datetime
    auth_provider: str = "google"
    is_active: bool = True
    tenant_id: int | None = None
    employee_id: int | None = None
    unread_count: int = 0
    slots_count: int = 0
    has_slots: bool = False

    model_config = ConfigDict(from_attributes=True)


class AdminUserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    auth_provider: str
    tenant_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateUserRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "reviewer"
    tenant_id: int | None = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UpdateUserRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None
    tenant_id: int | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Name is required")
        return trimmed

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class PaginatedUserResponse(BaseModel):
    data: list[UserResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


class PaginatedAdminUserResponse(BaseModel):
    data: list[AdminUserResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


class UserJobAssignment(BaseModel):
    hiring_request_id: UUID
    job_title: str
    created_at: datetime


class UserJobAssignmentsResponse(BaseModel):
    user_id: int
    name: str
    email: str
    role: str
    is_active: bool
    total: int
    data: list[UserJobAssignment]
