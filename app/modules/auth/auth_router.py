from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.auth.auth_dependencies import get_current_user
from app.modules.auth.auth_schema import (
    AuthMeResponse,
    GoogleLoginRequest,
    LogoutRequest,
    RefreshRequest,
    RefreshTokenResponse,
    TokenResponse,
    UserInfo,
)
from app.modules.auth.auth_service import AuthError, AuthService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/auth", tags=["auth"])


@router.post("/google", response_model=TokenResponse)
def google_login(body: GoogleLoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)

    google_info = service.verify_google_token(body.credential)
    user = service.find_or_create_user(google_info)
    access_token, refresh_token, expires_in = service.create_tokens(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    try:
        access_token, expires_in = service.refresh_access_token(body.refresh_token)
        return RefreshTokenResponse(access_token=access_token, expires_in=expires_in)
    except AuthError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/me", response_model=AuthMeResponse)
def auth_me(current_user: UserInfo = Depends(get_current_user)):
    return AuthMeResponse(user=current_user)


@router.post("/logout")
def logout(body: LogoutRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    service.revoke_refresh_token(body.refresh_token)
    return {"message": "Logged out successfully"}
