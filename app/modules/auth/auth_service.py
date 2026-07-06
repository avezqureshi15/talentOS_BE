import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jose import JWTError, jwt
from passlib.hash import bcrypt
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import ErrorCode
from app.core.logger import get_logger
from app.common.exceptions.base_exception import BaseAppException
from app.modules.auth.auth_model import RefreshToken
from app.modules.auth.auth_schema import UserInfo
from app.modules.users.user_model import User

logger = get_logger(__name__)


class AuthError(BaseAppException):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message=message, code=ErrorCode.UNAUTHORIZED, status_code=status_code)


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    # ── Google token verification ──────────────────────────────────────────

    def verify_google_token(self, credential: str) -> dict:
        try:
            info = id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
            if info.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
                raise AuthError("Invalid token issuer")
            return info
        except ValueError as exc:
            raise AuthError(f"Invalid Google token: {exc}")

    # ── User lookup / creation ─────────────────────────────────────────────

    def find_or_create_user(self, google_info: dict) -> User:
        email = google_info["email"]
        domain = email.split("@")[1].lower() if "@" in email else ""

        allowed = settings.ALLOWED_EMAIL_DOMAIN.lower().strip()
        if allowed and domain != allowed:
            raise AuthError(
                f"Only @{allowed} email addresses are allowed to access this platform.",
                status_code=403,
            )

        user = self.db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user:
            logger.info("Existing user logged in: email=%s id=%d", email, user.id)
            return user

        now = datetime.now(timezone.utc)
        name = google_info.get("name", email.split("@")[0])

        user = User(
            emp_id=f"u{secrets.token_hex(8)}",
            email=email,
            name=name,
            status="active",
            user_type="employee",
            designation="Unassigned",
            department="Unassigned",
            role="user",
            work_mode="remote",
            delivery_status="active",
            work_location_type="remote",
            doj=now.date(),
            date_of_birth=now.date(),
            band="L1",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info("New user created from Google login: email=%s id=%d", email, user.id)
        return user

    # ── JWT token management ──────────────────────────────────────────────

    def _create_access_token(self, user_id: int) -> tuple[str, int]:
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "type": "access",
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        return token, expires_in

    def _create_refresh_token(self, user_id: int) -> str:
        raw_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        self.db.add(RefreshToken(
            token_hash=token_hash,
            user_id=user_id,
            expires_at=expires_at,
        ))
        self.db.commit()
        return raw_token

    def create_tokens(self, user_id: int) -> tuple[str, str, int]:
        access_token, expires_in = self._create_access_token(user_id)
        refresh_token = self._create_refresh_token(user_id)
        return access_token, refresh_token, expires_in

    def refresh_access_token(self, raw_refresh_token: str) -> tuple[str, int]:
        token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        record = self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            ),
        ).scalar_one_or_none()

        if not record:
            raise AuthError("Invalid or expired refresh token")

        access_token, expires_in = self._create_access_token(record.user_id)
        return access_token, expires_in

    def revoke_refresh_token(self, raw_refresh_token: str) -> None:
        token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        self.db.execute(delete(RefreshToken).where(RefreshToken.token_hash == token_hash))
        self.db.commit()

    def get_current_user(self, token: str) -> UserInfo:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            if payload.get("type") != "access":
                raise AuthError("Invalid token type")
            user_id = int(payload["sub"])
        except (JWTError, KeyError, ValueError) as exc:
            raise AuthError(f"Invalid or expired access token: {exc}")

        user = self.db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            raise AuthError("User not found")
        return UserInfo(id=user.id, email=user.email, name=user.name)
