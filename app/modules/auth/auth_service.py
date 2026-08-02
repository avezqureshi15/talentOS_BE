import hashlib
import secrets
import threading
from datetime import datetime, timedelta, timezone

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import ErrorCode
from app.core.logger import get_logger
from app.core.security import hash_password, verify_password
from app.common.exceptions.base_exception import BaseAppException
from app.modules.auth.auth_repository import AuthRepository
from app.modules.auth.auth_schema import UserInfo
from app.modules.tenants.tenant_model import Tenant
from app.modules.users.permission_service import PermissionService

logger = get_logger(__name__)


class AuthError(BaseAppException):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message=message, code=ErrorCode.UNAUTHORIZED, status_code=status_code)


INVITE_TOKEN_BYTES = 48
INVITE_EXPIRE_DAYS = 7


_google_request_session: google_requests.Request | None = None
_google_session_lock = threading.Lock()


def _get_google_session() -> google_requests.Request:
    global _google_request_session
    if _google_request_session is None:
        with _google_session_lock:
            if _google_request_session is None:
                _google_request_session = google_requests.Request()
    return _google_request_session


class AuthService:
    def __init__(self, db: Session):
        self.repo = AuthRepository(db)
        self.db = db

    def _build_user_info(self, user) -> UserInfo:
        perm_service = PermissionService(self.db)
        permissions = perm_service.get_permissions_for_role(user.role)
        return UserInfo(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            tenant_id=user.tenant_id,
            auth_provider=user.auth_provider,
            is_active=user.is_active,
            permissions=permissions,
        )

    # ── Google token verification ──────────────────────────────────────────

    def verify_google_token(self, credential: str) -> dict:
        try:
            info = id_token.verify_oauth2_token(
                credential,
                _get_google_session(),
                settings.GOOGLE_CLIENT_ID,
            )
            if info.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
                raise AuthError("Invalid token issuer")
            return info
        except ValueError as exc:
            raise AuthError(f"Invalid Google token: {exc}")

    # ── Email / password login ─────────────────────────────────────────────

    def login_with_email(self, email: str, password: str) -> tuple[object, str, str, int]:
        user = self.repo.get_user_by_email(email)
        if not user:
            raise AuthError("Invalid email or password")

        if not user.password_hash:
            raise AuthError("This account uses Google Sign-In. Please sign in with Google.")

        if not verify_password(password, user.password_hash):
            raise AuthError("Invalid email or password")

        if not user.is_active:
            raise AuthError("Your account has been deactivated. Contact your administrator.", status_code=423)

        if user.tenant_id:
            tenant = self.db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            if tenant and tenant.verification_status != "approved":
                raise AuthError(
                    "Your organization is not yet verified. Please contact support.",
                    status_code=403,
                )

        access_token, refresh_token, expires_in = self.create_tokens(user.id)
        return user, access_token, refresh_token, expires_in

    # ── Signup (create tenant + admin user) ────────────────────────────────

    def signup(self, email: str, password: str, full_name: str, org_name: str) -> tuple[object, str, str, int]:
        if not settings.ALLOW_SIGNUP:
            raise AuthError(
                "Registration is invite-only. Please contact your administrator to get invited.",
                status_code=403,
            )

        domain = email.split("@")[1].lower() if "@" in email else ""
        allowed = settings.ALLOWED_EMAIL_DOMAIN.lower().strip()
        if allowed and allowed != "all" and domain != allowed:
            raise AuthError(
                f"Only @{allowed} email addresses are allowed to access this platform.",
                status_code=403,
            )

        existing = self.repo.get_user_by_email(email)
        if existing:
            raise AuthError("An account with this email already exists")

        slug = org_name.lower().replace(" ", "-").replace("--", "-")[:80]
        base_slug = slug
        counter = 1
        while self.db.query(Tenant).filter(Tenant.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        tenant = Tenant(name=org_name, slug=slug, is_active=False, verification_status="pending")
        self.db.add(tenant)
        self.db.flush()

        user = self.repo.create_user(
            commit=False,
            emp_id=f"u{secrets.token_hex(8)}",
            email=email,
            name=full_name,
            password_hash=hash_password(password),
            auth_provider="email",
            tenant_id=tenant.id,
            role="account_admin",
            status="active",
            user_type="employee",
            designation="Unassigned",
            department="Unassigned",
            work_mode="remote",
            delivery_status="active",
            work_location_type="remote",
            doj=datetime.now(timezone.utc).date(),
            date_of_birth=datetime.now(timezone.utc).date(),
            band="L1",
        )

        self.db.commit()
        access_token, refresh_token, expires_in = self.create_tokens(user.id)
        return user, access_token, refresh_token, expires_in

    # ── Change password ────────────────────────────────────────────────────

    def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
        user = self.repo.get_user_by_id(user_id)
        if not user:
            raise AuthError("User not found")

        if not user.password_hash:
            raise AuthError("Cannot change password for Google-authenticated accounts")

        if not verify_password(old_password, user.password_hash):
            raise AuthError("Current password is incorrect")

        user.password_hash = hash_password(new_password)
        self.db.commit()
        logger.info("Password changed for user_id=%d", user_id)

    # ── Invite flow ────────────────────────────────────────────────────────

    def get_invite(self, token: str) -> dict:
        from app.modules.auth.invite_model import TenantInvite

        invite = self.db.query(TenantInvite).filter(
            TenantInvite.token == token,
            TenantInvite.accepted_at.is_(None),
            TenantInvite.expires_at > datetime.now(timezone.utc),
        ).first()
        if not invite:
            raise AuthError("Invalid or expired invite token")

        tenant = self.db.query(Tenant).filter(Tenant.id == invite.tenant_id).first()
        return {
            "email": invite.email,
            "role": invite.role,
            "org_name": tenant.name if tenant else "",
            "tenant_id": invite.tenant_id,
        }

    def accept_invite(self, token: str, password: str, full_name: str) -> tuple[object, str, str, int]:
        from app.modules.auth.invite_model import TenantInvite

        invite = self.db.query(TenantInvite).filter(
            TenantInvite.token == token,
            TenantInvite.accepted_at.is_(None),
            TenantInvite.expires_at > datetime.now(timezone.utc),
        ).first()
        if not invite:
            raise AuthError("Invalid or expired invite token")

        existing = self.repo.get_user_by_email(invite.email)
        if existing:
            raise AuthError("A user with this email already exists")

        user = self.repo.create_user(
            commit=False,
            emp_id=f"u{secrets.token_hex(8)}",
            email=invite.email,
            name=full_name,
            password_hash=hash_password(password),
            auth_provider="email",
            tenant_id=invite.tenant_id,
            role=invite.role,
            status="active",
            user_type="employee",
            designation="Unassigned",
            department="Unassigned",
            work_mode="remote",
            delivery_status="active",
            work_location_type="remote",
            doj=datetime.now(timezone.utc).date(),
            date_of_birth=datetime.now(timezone.utc).date(),
            band="L1",
        )

        invite.accepted_at = datetime.now(timezone.utc)
        self.db.commit()

        access_token, refresh_token, expires_in = self.create_tokens(user.id)
        return user, access_token, refresh_token, expires_in

    # ── User lookup / creation (Google) ─────────────────────────────────────

    def find_or_create_user(self, google_info: dict):
        email = google_info["email"]
        domain = email.split("@")[1].lower() if "@" in email else ""

        allowed = settings.ALLOWED_EMAIL_DOMAIN.lower().strip()
        if allowed and allowed != "all" and domain != allowed:
            raise AuthError(
                f"Only @{allowed} email addresses are allowed to access this platform.",
                status_code=403,
            )

        user = self.repo.get_user_by_email(email)
        if user:
            if not user.is_active:
                raise AuthError("Your account has been deactivated.", status_code=423)
            logger.info("Existing user logged in: email=%s id=%d", email, user.id)
            return user

        raise AuthError(
            "You don't have an account yet. Please contact your administrator to get invited.",
            status_code=403,
        )

    # ── JWT token management ──────────────────────────────────────────────

    def _create_access_token(self, user_id: int, user_role: str = "recruiter", user_tenant_id: int | None = None, auth_provider: str = "google", permissions: list[str] | None = None) -> tuple[str, int]:
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),
            "role": user_role,
            "tenant_id": user_tenant_id,
            "auth_provider": auth_provider,
            "perms": permissions or [],
            "exp": expire,
            "type": "access",
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        return token, expires_in

    def _create_refresh_token(self, user_id: int) -> str:
        raw_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        self.repo.create_refresh_token(token_hash, user_id, expires_at)
        return raw_token

    def create_tokens(self, user_id: int) -> tuple[str, str, int]:
        user = self.repo.get_user_by_id(user_id)
        perm_service = PermissionService(self.db)
        permissions = perm_service.get_permissions_for_role(user.role)
        access_token, expires_in = self._create_access_token(
            user_id,
            user_role=user.role,
            user_tenant_id=user.tenant_id,
            auth_provider=user.auth_provider,
            permissions=permissions,
        )
        refresh_token = self._create_refresh_token(user_id)
        return access_token, refresh_token, expires_in

    def refresh_access_token(self, raw_refresh_token: str) -> tuple[str, int]:
        token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        record = self.repo.get_refresh_token_by_hash(token_hash)
        if not record:
            raise AuthError("Invalid or expired refresh token")
        user = self.repo.get_user_by_id(record.user_id)
        perm_service = PermissionService(self.db)
        permissions = perm_service.get_permissions_for_role(user.role if user else "recruiter")
        access_token, expires_in = self._create_access_token(
            record.user_id,
            user_role=user.role if user else "recruiter",
            user_tenant_id=user.tenant_id if user else None,
            auth_provider=user.auth_provider if user else "google",
            permissions=permissions,
        )
        return access_token, expires_in

    def revoke_refresh_token(self, raw_refresh_token: str) -> None:
        token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        self.repo.delete_refresh_token_by_hash(token_hash)

    def get_current_user(self, token: str) -> UserInfo:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            if payload.get("type") != "access":
                raise AuthError("Invalid token type")
            user_id = int(payload["sub"])
        except (JWTError, KeyError, ValueError) as exc:
            raise AuthError(f"Invalid or expired access token: {exc}")

        user = self.repo.get_user_by_id(user_id)
        if not user:
            raise AuthError("User not found")

        user_info = self._build_user_info(user)
        jwt_perms = payload.get("perms", [])
        if jwt_perms:
            user_info.permissions = jwt_perms
        return user_info
