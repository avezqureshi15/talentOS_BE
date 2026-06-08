from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.core.dependencies import get_current_user
from app.models.user import AllowedUser
from app.schemas.auth import TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/google/login")
async def google_login():
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}")


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        # Get user info
        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")

        user_info = user_resp.json()
        email = user_info.get("email")

        if not email:
            raise HTTPException(status_code=400, detail="No email in Google response")

    # Check allowlist
    result = await db.execute(
        select(AllowedUser).where(
            AllowedUser.email == email,
            AllowedUser.is_active == True,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Contact your HR admin.",
        )

    jwt_token = create_access_token(data={"sub": email, "role": user.role})
    return TokenResponse(access_token=jwt_token)


@router.get("/me", response_model=UserOut)
async def get_me(current_user: AllowedUser = Depends(get_current_user)):
    return current_user


@router.post("/logout")
async def logout():
    # JWT is stateless — client drops the token
    return {"message": "Logged out successfully"}
