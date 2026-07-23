from pydantic import BaseModel, ConfigDict, EmailStr


class CreateInviteRequest(BaseModel):
    email: EmailStr
    role: str
    tenant_id: int | None = None


class InviteResponse(BaseModel):
    id: int
    email: str
    role: str
    token: str
    expires_at: str
    accepted_at: str | None = None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class PaginatedInviteResponse(BaseModel):
    data: list[InviteResponse]
    total: int
    page: int
    per_page: int
    has_more: bool
