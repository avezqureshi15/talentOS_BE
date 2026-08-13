from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CreateAppRequest(BaseModel):
    name: str
    description: str | None = None
    tenant_id: int | None = None
    role: str | None = None
    expires_at: datetime | None = None


class UpdateAppRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    role: str | None = None
    expires_at: datetime | None = None


class CreatedByBrief(BaseModel):
    id: int
    name: str | None = None
    email: str | None = None


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    key_prefix: str
    tenant_id: int | None = None
    tenant_name: str | None = None
    role: str | None = None
    is_active: bool
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime
    created_by: CreatedByBrief | None = None

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreatedResponse(ApiKeyResponse):
    full_key: str


class ApiKeyListResponse(BaseModel):
    data: list[ApiKeyResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


class PermissionInfo(BaseModel):
    code: str
    name: str
    group: str
    assigned: bool = False
    endpoint: str = ""

    model_config = ConfigDict(from_attributes=True)


class ApiKeyDetailResponse(ApiKeyResponse):
    permissions: list[PermissionInfo]


class UpdatePermissionsRequest(BaseModel):
    permission_codes: list[str]
