from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class GoogleLoginRequest(BaseModel):
    credential: str


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    org_name: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters")
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfo(BaseModel):
    id: int
    email: str
    name: str
    picture: str | None = None
    role: str
    tenant_id: int | None = None
    auth_provider: str
    is_active: bool
    permissions: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class AuthMeResponse(BaseModel):
    user: UserInfo


class LogoutRequest(BaseModel):
    refresh_token: str


class InviteInfo(BaseModel):
    email: str
    role: str
    org_name: str
    tenant_id: int


class AcceptInviteRequest(BaseModel):
    token: str
    password: str
    full_name: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v
