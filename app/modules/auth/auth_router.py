from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import get_logger
from app.db.session import get_db
from app.modules.auth.auth_dependencies import get_current_user
from app.modules.auth.auth_schema import (
    AcceptInviteRequest,
    AuthMeResponse,
    ChangePasswordRequest,
    EmailLoginRequest,
    GoogleLoginRequest,
    InviteInfo,
    LogoutRequest,
    RefreshRequest,
    RefreshTokenResponse,
    SignupRequest,
    TokenResponse,
    UserInfo,
)
from app.modules.auth.auth_service import AuthError, AuthService

logger = get_logger(__name__)

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


@router.post("/login", response_model=TokenResponse)
def email_login(body: EmailLoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    try:
        user, access_token, refresh_token, expires_in = service.login_with_email(
            email=body.email, password=body.password
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/signup", response_model=TokenResponse)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    try:
        user, access_token, refresh_token, expires_in = service.signup(
            email=body.email, password=body.password, full_name=body.full_name, org_name=body.org_name
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = AuthService(db)
    try:
        service.change_password(current_user.id, body.old_password, body.new_password)
        return {"message": "Password changed successfully"}
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/invites/{token}", response_model=InviteInfo)
def get_invite(token: str, db: Session = Depends(get_db)):
    service = AuthService(db)
    try:
        invite = service.get_invite(token)
        return InviteInfo(**invite)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/accept-invite", response_model=TokenResponse)
def accept_invite(body: AcceptInviteRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    try:
        user, access_token, refresh_token, expires_in = service.accept_invite(
            token=body.token, password=body.password, full_name=body.full_name
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    try:
        access_token, expires_in = service.refresh_access_token(body.refresh_token)
        return RefreshTokenResponse(access_token=access_token, expires_in=expires_in)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/me", response_model=AuthMeResponse)
def auth_me(current_user: UserInfo = Depends(get_current_user)):
    return AuthMeResponse(user=current_user)


@router.post("/logout")
def logout(body: LogoutRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    service.revoke_refresh_token(body.refresh_token)
    return {"message": "Logged out successfully"}
