from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.logger import get_logger
from app.core.secrets import (
    MANAGEABLE_API_KEYS,
    decrypt_secret,
    encrypt_secret,
    mask_secret,
)
from app.modules.settings.settings_model import TenantSetting
from app.modules.settings.settings_schema import (
    ApiKeyEntry,
    ApiKeysResponse,
    SettingEntry,
    SettingsResponse,
)

logger = get_logger(__name__)


class SettingsService:
    def __init__(self, db: Session):
        self.db = db

    def get_settings(self, tenant_id: int) -> SettingsResponse:
        rows = self.db.query(TenantSetting).filter(
            TenantSetting.tenant_id == tenant_id
        ).all()
        settings = [SettingEntry(key=r.key, value=r.value) for r in rows]
        return SettingsResponse(settings=settings)

    def update_settings(self, tenant_id: int, entries: list[SettingEntry]) -> SettingsResponse:
        for entry in entries:
            existing = self.db.query(TenantSetting).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.key == entry.key,
            ).first()
            if existing:
                existing.value = entry.value
            else:
                self.db.add(TenantSetting(tenant_id=tenant_id, key=entry.key, value=entry.value))
        self.db.commit()
        logger.info("Updated %d settings for tenant_id=%d", len(entries), tenant_id)
        return self.get_settings(tenant_id)

    # ── API keys (superadmin only, Fernet-encrypted) ─────────────────────

    def get_api_keys(self, tenant_id: int) -> ApiKeysResponse:
        rows = {
            r.key: r.value
            for r in self.db.query(TenantSetting).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.key.in_(MANAGEABLE_API_KEYS),
            ).all()
        }
        keys: list[ApiKeyEntry] = []
        for key in MANAGEABLE_API_KEYS:
            stored = rows.get(key)
            if stored:
                keys.append(
                    ApiKeyEntry(
                        key=key,
                        value=mask_secret(decrypt_secret(stored)),
                        hasOverride=True,
                        source="tenant",
                    )
                )
            else:
                env_value = getattr(app_settings, key, "") or ""
                keys.append(
                    ApiKeyEntry(
                        key=key,
                        value=mask_secret(env_value) if env_value else "",
                        hasOverride=False,
                        source="platform",
                    )
                )
        return ApiKeysResponse(keys=keys)

    def update_api_keys(self, tenant_id: int, entries: list[SettingEntry]) -> ApiKeysResponse:
        for entry in entries:
            if entry.key not in MANAGEABLE_API_KEYS:
                raise ValueError(f"Key not manageable: {entry.key}")
            existing = self.db.query(TenantSetting).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.key == entry.key,
            ).first()
            value = (entry.value or "").strip()
            if not value:
                if existing:
                    self.db.delete(existing)
                continue
            encrypted = encrypt_secret(value)
            if existing:
                existing.value = encrypted
            else:
                self.db.add(TenantSetting(tenant_id=tenant_id, key=entry.key, value=encrypted))
        self.db.commit()
        logger.info("Updated %d API key(s) for tenant_id=%d", len(entries), tenant_id)
        return self.get_api_keys(tenant_id)
