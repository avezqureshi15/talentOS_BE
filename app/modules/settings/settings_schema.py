from pydantic import BaseModel


class SettingEntry(BaseModel):
    key: str
    value: str


class SettingsResponse(BaseModel):
    settings: list[SettingEntry]


class UpdateSettingsRequest(BaseModel):
    settings: list[SettingEntry]
    tenant_id: int | None = None
