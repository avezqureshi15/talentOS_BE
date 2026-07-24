from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class CreateTenantRequest(BaseModel):
    org_name: str
    admin_name: str
    admin_email: EmailStr


class UpdateTenantRequest(BaseModel):
    name: str | None = None
    verification_status: str | None = None
    is_active: bool | None = None


class TenantResponse(BaseModel):
    id: int
    name: str
    slug: str
    is_active: bool
    verification_status: str
    user_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedTenantResponse(BaseModel):
    data: list[TenantResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


class TenantAdminDetails(BaseModel):
    tenant_id: int
    name: str
    slug: str
    admin_email: str
    admin_name: str
    invite_token: str
    expires_at: str
