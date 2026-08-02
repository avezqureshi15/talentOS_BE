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
from app.modules.settings.settings_model import TenantSetting

logger = get_logger(__name__)

# Keys an admin may manage from the superadmin dashboard.
MANAGEABLE_API_KEYS: list[str] = [
    "RH_API_KEY",
    "SERVICE_API_KEY",
    "MEETMIND_API_TOKEN",
    "SUPABASE_SERVICE_ROLE_KEY",
    "RESEND_API_KEY",
]

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


def get_secret(name: str, tenant_id: int | None = None) -> str:
    """Return the effective secret for *name*: tenant override or platform env value."""
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
    return getattr(settings, name, "") or ""
