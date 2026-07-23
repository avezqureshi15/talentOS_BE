from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.settings.settings_model import TenantSetting
from app.modules.settings.settings_schema import SettingEntry, SettingsResponse

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
