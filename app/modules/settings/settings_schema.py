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


class ApiKeysResponse(BaseModel):
    keys: list[ApiKeyEntry]


class UpdateApiKeysRequest(BaseModel):
    keys: list[SettingEntry]
    tenant_id: int | None = None
