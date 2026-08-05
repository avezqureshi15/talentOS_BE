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
    employee_count: int = 0
    logo_url: str | None = None
    website: str | None = None
    phone: str | None = None
    description: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    gst_number: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedTenantResponse(BaseModel):
    data: list[TenantResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


class UpdateOrganizationRequest(BaseModel):
    logo_url: str | None = None
    website: str | None = None
    phone: str | None = None
    description: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    gst_number: str | None = None


class TenantAdminDetails(BaseModel):
    tenant_id: int
    name: str
    slug: str
    admin_email: str
    admin_name: str
    invite_token: str
    expires_at: str
