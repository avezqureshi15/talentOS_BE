from pydantic import BaseModel, EmailStr
from datetime import datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
