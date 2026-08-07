import json

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.logger import get_logger
from app.core.ai_recruitment_client import AiRecruitmentClient
from app.core.secrets import (
    MANAGEABLE_API_KEYS,
    decrypt_secret,
    encrypt_secret,
    mask_secret,
)
from app.modules.settings.settings_model import TenantSetting
from app.modules.settings.settings_schema import (
    AiScreeningSettings,
    AiScreeningSettingsUpdate,
    ApiKeyEntry,
    ApiKeysResponse,
    SettingEntry,
    SettingsResponse,
)

logger = get_logger(__name__)

AI_SCREENING_SETTINGS_KEY = "ai_screening"

AI_SCREENING_DEFAULTS: dict = {
    "enforce_phone_geography": False,
    "allowed_phone_regions": [],
    "screening_enabled": True,
    "screening_max_retries": 3,
    "screening_retry_delay_seconds": 1800,
}


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

    # ── AI screening settings (per tenant, JSON payload) ──────────────────

    def _get_stored_row(self, tenant_id: int) -> TenantSetting | None:
        return self.db.query(TenantSetting).filter(
            TenantSetting.tenant_id == tenant_id,
            TenantSetting.key == AI_SCREENING_SETTINGS_KEY,
        ).first()

    def _row_to_settings(self, row: TenantSetting) -> AiScreeningSettings:
        try:
            data = json.loads(row.value or "{}")
        except ValueError:
            data = {}
        merged = {**AI_SCREENING_DEFAULTS, **data}
        return AiScreeningSettings(
            enforce_phone_geography=bool(merged["enforce_phone_geography"]),
            allowed_phone_regions=[str(r) for r in merged["allowed_phone_regions"]],
            screening_enabled=bool(merged["screening_enabled"]),
            screening_max_retries=int(merged["screening_max_retries"]),
            screening_retry_delay_seconds=int(merged["screening_retry_delay_seconds"]),
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
            source="tenant",
        )

    async def get_ai_screening_settings(self, tenant_id: int) -> AiScreeningSettings:
        row = self._get_stored_row(tenant_id)
        if row:
            return self._row_to_settings(row)

        # No tenant override yet — seed from the POC so the UI never contradicts
        # what the screening pipeline actually enforces.
        try:
            poc = await AiRecruitmentClient().get_settings()
            if isinstance(poc, dict):
                return AiScreeningSettings(
                    enforce_phone_geography=bool(poc.get("enforce_phone_geography")),
                    allowed_phone_regions=[str(r) for r in (poc.get("allowed_phone_regions") or [])],
                    screening_enabled=bool(poc.get("screening_enabled", True)),
                    screening_max_retries=int(poc.get("screening_max_retries") or AI_SCREENING_DEFAULTS["screening_max_retries"]),
                    screening_retry_delay_seconds=int(poc.get("screening_retry_delay_seconds") or AI_SCREENING_DEFAULTS["screening_retry_delay_seconds"]),
                    updated_at=poc.get("updated_at"),
                    source="poc",
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("POC settings fallback failed for tenant_id=%d: %s", tenant_id, exc)

        return AiScreeningSettings(**AI_SCREENING_DEFAULTS, source="default")

    async def update_ai_screening_settings(
        self,
        tenant_id: int,
        payload: AiScreeningSettingsUpdate,
    ) -> AiScreeningSettings:
        current = await self.get_ai_screening_settings(tenant_id)
        data = {
            "enforce_phone_geography": (
                payload.enforce_phone_geography
                if payload.enforce_phone_geography is not None
                else current.enforce_phone_geography
            ),
            "allowed_phone_regions": [
                str(r).strip().upper()
                for r in (
                    payload.allowed_phone_regions
                    if payload.allowed_phone_regions is not None
                    else current.allowed_phone_regions
                )
            ],
            "screening_enabled": (
                payload.screening_enabled
                if payload.screening_enabled is not None
                else current.screening_enabled
            ),
            "screening_max_retries": (
                payload.screening_max_retries
                if payload.screening_max_retries is not None
                else current.screening_max_retries
            ),
            "screening_retry_delay_seconds": (
                payload.screening_retry_delay_seconds
                if payload.screening_retry_delay_seconds is not None
                else current.screening_retry_delay_seconds
            ),
        }
        if data["enforce_phone_geography"] and not data["allowed_phone_regions"]:
            raise ValueError("Geography enforcement requires at least one allowed region")
        if not (1 <= data["screening_max_retries"] <= 9):
            raise ValueError("screening_max_retries must be between 1 and 9")
        if data["screening_retry_delay_seconds"] < 0:
            raise ValueError("screening_retry_delay_seconds cannot be negative")
        data["allowed_phone_regions"] = list(dict.fromkeys(data["allowed_phone_regions"]))

        existing = self._get_stored_row(tenant_id)
        if existing:
            existing.value = json.dumps(data)
        else:
            self.db.add(TenantSetting(tenant_id=tenant_id, key=AI_SCREENING_SETTINGS_KEY, value=json.dumps(data)))
        self.db.commit()
        logger.info("Updated ai-screening settings for tenant_id=%d", tenant_id)

        # Best-effort sync to the POC so its pipeline enforces the same config.
        try:
            await AiRecruitmentClient().update_settings(
                {k: data[k] for k in AI_SCREENING_DEFAULTS}
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("POC ai-screening sync failed for tenant_id=%d: %s", tenant_id, exc)

        return await self.get_ai_screening_settings(tenant_id)
