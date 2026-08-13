"""Encrypted, tenant-scoped secret store with platform (.env) fallback.

Secrets are stored Fernet-encrypted in the existing ``tenant_settings`` table
as ``enc:v1:<token>``. The data-encryption key is derived from
``SECRETS_ENCRYPTION_KEY`` (fallback: ``JWT_SECRET``) so no extra deployment
step is required.

Lookup order: tenant override (decrypted) -> platform ``settings`` value.
The tenant is resolved from a per-request ``ContextVar`` set by
:class:`TenantContextMiddleware`; callers without a request (workers) fall
back to the platform value.
"""

import base64
import hashlib
from contextvars import ContextVar

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.settings.settings_model import PlatformSetting, TenantSetting

logger = get_logger(__name__)

# Keys an admin may manage from the superadmin dashboard.
# scope:
#   "platform" — global value stored in platform_settings; resolved for inbound
#       callbacks / workers that have no tenant context, then env as fallback.
#   "tenant"   — per-tenant override stored in tenant_settings; resolved when a
#       tenant context exists, then platform/env as fallback.
# is_secret: False values (base URLs etc.) are shown unmasked in the settings UI.
MANAGEABLE_API_KEY_META: list[dict[str, str | bool]] = [
    {
        "key": "RH_SERVICE_URL",
        "label": "Recruitment hub base URL",
        "icon": "bx bx-link",
        "hint": "Base URL of the Recruitment hub (ai-recruitment-poc) service used by all BE -> RH calls.",
        "scope": "tenant",
        "is_secret": False,
    },
    {
        "key": "SERVICE_API_KEY",
        "label": "Incoming service callbacks",
        "icon": "bx bx-shield-quarter",
        "hint": "Shared secret the ai-recruitment-poc uses to call talentOS internal endpoints.",
        "scope": "platform",
        "is_secret": True,
    },
    {
        "key": "RH_API_KEY",
        "label": "Recruitment hub API key",
        "icon": "bx bx-code-alt",
        "hint": "Bearer key used for the Recruitment hub service (jobs, candidates, screening, interviews).",
        "scope": "tenant",
        "is_secret": True,
    },
    {
        "key": "MEETMIND_BASE_URL",
        "label": "MeetMind base URL",
        "icon": "bx bx-link",
        "hint": "Base URL used when registering Google Meet interview schedules with MeetMind.",
        "scope": "tenant",
        "is_secret": False,
    },
    {
        "key": "MEETMIND_API_TOKEN",
        "label": "MeetMind API token",
        "icon": "bx bx-code-alt",
        "hint": "X-API-Key used when registering Google Meet interview schedules with MeetMind.",
        "scope": "tenant",
        "is_secret": True,
    },
    {
        "key": "MEETMIND_WEBHOOK_SECRET",
        "label": "MeetMind webhook secret",
        "icon": "bx bx-shield-quarter",
        "hint": "HMAC secret used to verify X-Signature on MeetMind transcript webhooks.",
        "scope": "platform",
        "is_secret": True,
    },
    {
        "key": "MEETMIND_EXTERNAL",
        "label": "MeetMind external domain",
        "icon": "bx bx-globe",
        "hint": "External identifier sent in the MeetMind schedule payload (defaults to talentos.ai).",
        "scope": "tenant",
        "is_secret": False,
    },
]

MANAGEABLE_API_KEYS: list[str] = [str(m["key"]) for m in MANAGEABLE_API_KEY_META]
PLATFORM_SCOPE_KEYS: set[str] = {
    str(m["key"]) for m in MANAGEABLE_API_KEY_META if m.get("scope") == "platform"
}
TENANT_SCOPE_KEYS: set[str] = {
    str(m["key"]) for m in MANAGEABLE_API_KEY_META if m.get("scope") == "tenant"
}

PREFIX = "enc:v1:"

current_tenant_id: ContextVar[int | None] = ContextVar("current_tenant_id", default=None)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        source = settings.SECRETS_ENCRYPTION_KEY or settings.JWT_SECRET
        key = base64.urlsafe_b64encode(hashlib.sha256(source.encode()).digest())
        _fernet = Fernet(key)
    return _fernet


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret for storage. Empty input stays empty."""
    if not plaintext:
        return plaintext
    return PREFIX + _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(stored: str) -> str:
    """Decrypt a stored secret. Raises InvalidToken when undecryptable."""
    if not stored:
        return stored
    if not stored.startswith(PREFIX):
        return stored
    return _get_fernet().decrypt(stored[len(PREFIX):].encode()).decode()


def mask_secret(value: str) -> str:
    """Mask a secret for display — never returns the full value."""
    if not value:
        return ""
    return f"••••{value[-4:]}"


def _lookup_override(key: str, tenant_id: int) -> str | None:
    try:
        with SessionLocal() as db:
            row = (
                db.query(TenantSetting)
                .filter(
                    TenantSetting.tenant_id == tenant_id,
                    TenantSetting.key == key,
                )
                .first()
            )
            return row.value if row else None
    except Exception as exc:
        logger.warning("Secret override lookup failed for %s: %s", key, exc)
        return None


def _lookup_platform(key: str) -> str | None:
    try:
        with SessionLocal() as db:
            row = (
                db.query(PlatformSetting)
                .filter(PlatformSetting.key == key)
                .first()
            )
            return row.value if row else None
    except Exception as exc:
        logger.warning("Platform secret lookup failed for %s: %s", key, exc)
        return None


def get_secret(name: str, tenant_id: int | None = None) -> str:
    """Return the effective secret for *name*.

    Resolution order: tenant override (when a tenant is known) -> platform
    (global) value -> platform ``settings`` env value.
    """
    tid = tenant_id if tenant_id is not None else current_tenant_id.get()
    if tid is not None:
        stored = _lookup_override(name, tid)
        if stored is not None:
            try:
                return decrypt_secret(stored)
            except InvalidToken:
                logger.warning(
                    "Secret %s override unreadable (encryption key rotated?) — using platform value", name
                )
    platform_stored = _lookup_platform(name)
    if platform_stored is not None:
        try:
            return decrypt_secret(platform_stored)
        except InvalidToken:
            logger.warning(
                "Platform secret %s unreadable (encryption key rotated?) — using env value", name
            )
    return getattr(settings, name, "") or ""
