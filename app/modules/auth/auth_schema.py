from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GoogleLoginRequest(BaseModel):
    credential: str


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

    model_config = ConfigDict(from_attributes=True)


class AuthMeResponse(BaseModel):
    user: UserInfo


class LogoutRequest(BaseModel):
    refresh_token: str
