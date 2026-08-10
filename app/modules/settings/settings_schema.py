from typing import Literal

from pydantic import BaseModel


class SettingEntry(BaseModel):
    key: str
    value: str


class SettingsResponse(BaseModel):
    settings: list[SettingEntry]


class UpdateSettingsRequest(BaseModel):
    settings: list[SettingEntry]
    tenant_id: int | None = None


class ApiKeyEntry(BaseModel):
    key: str
    value: str = ""
    hasOverride: bool = False
    source: Literal["tenant", "platform"] = "platform"
    scope: Literal["platform", "tenant"] = "tenant"
    isSecret: bool = True


class ApiKeysResponse(BaseModel):
    keys: list[ApiKeyEntry]


class UpdateApiKeysRequest(BaseModel):
    keys: list[SettingEntry]
    tenant_id: int | None = None


class ManageableApiKeyMeta(BaseModel):
    key: str
    label: str
    icon: str
    hint: str
    scope: Literal["platform", "tenant"] = "tenant"
    is_secret: bool = True


class ManageableApiKeysResponse(BaseModel):
    keys: list[ManageableApiKeyMeta]


class AiScreeningSettings(BaseModel):
    """Per-tenant AI voice-screening configuration (mirrors POC system settings)."""

    enforce_phone_geography: bool = False
    allowed_phone_regions: list[str] = []
    screening_enabled: bool = True
    screening_max_retries: int = 3
    screening_retry_delay_seconds: int = 1800
    updated_at: str | None = None
    source: Literal["tenant", "poc", "default"] = "default"


class AiScreeningSettingsUpdate(BaseModel):
    enforce_phone_geography: bool | None = None
    allowed_phone_regions: list[str] | None = None
    screening_enabled: bool | None = None
    screening_max_retries: int | None = None
    screening_retry_delay_seconds: int | None = None
    tenant_id: int | None = None
