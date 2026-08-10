from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.db.session import get_db
from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.modules.auth.auth_schema import UserInfo
from app.core.secrets import MANAGEABLE_API_KEY_META
from app.modules.settings.settings_schema import (
    AiScreeningSettings,
    AiScreeningSettingsUpdate,
    ApiKeysResponse,
    ManageableApiKeyMeta,
    ManageableApiKeysResponse,
    SettingsResponse,
    UpdateApiKeysRequest,
    UpdateSettingsRequest,
)
from app.modules.settings.settings_service import SettingsService

router = APIRouter(
    prefix=f"{app_settings.API_V1_PREFIX}/settings",
    tags=["settings"],
    dependencies=[Depends(require_permission(Permission.SETTINGS_VIEW))],
)


def _resolve_tenant(current_user: UserInfo, tenant_id_override: int | None = None) -> int:
    if current_user.role == "superadmin":
        if tenant_id_override is None:
            raise HTTPException(status_code=400, detail="Superadmin must provide a tenant_id")
        return tenant_id_override
    if current_user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Admin user has no tenant")
    return current_user.tenant_id


def _require_superadmin(current_user: UserInfo) -> None:
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")


@router.get("", response_model=SettingsResponse)
def get_settings(
    tenant_id: int | None = Query(None, description="Required for superadmin"),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.SETTINGS_VIEW)),
):
    tid = _resolve_tenant(current_user, tenant_id)
    service = SettingsService(db)
    return service.get_settings(tid)


@router.patch("", response_model=SettingsResponse)
def update_settings(
    body: UpdateSettingsRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.SETTINGS_EDIT)),
):
    tid = _resolve_tenant(current_user, body.tenant_id)
    service = SettingsService(db)
    return service.update_settings(tid, body.settings)


# ── API keys (superadmin only) ────────────────────────────────────────────


@router.get("/api-keys/manageable", response_model=ManageableApiKeysResponse)
def get_manageable_api_keys(
    current_user: UserInfo = Depends(require_permission(Permission.SETTINGS_VIEW)),
):
    """Return the catalogue of API keys an admin may set (labels/icons/hints).

    The FE uses this to render the settings section without hardcoding the list.
    Superadmin-only, same as the value endpoints below.
    """
    _require_superadmin(current_user)
    return ManageableApiKeysResponse(
        keys=[ManageableApiKeyMeta(**meta) for meta in MANAGEABLE_API_KEY_META]
    )


@router.get("/api-keys", response_model=ApiKeysResponse)
def get_api_keys(
    tenant_id: int | None = Query(None, description="Required for superadmin to see tenant overrides; platform keys always included"),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.SETTINGS_VIEW)),
):
    _require_superadmin(current_user)
    return SettingsService(db).get_api_keys(tenant_id)


@router.patch("/api-keys", response_model=ApiKeysResponse)
def update_api_keys(
    body: UpdateApiKeysRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.SETTINGS_EDIT)),
):
    _require_superadmin(current_user)
    try:
        return SettingsService(db).update_api_keys(body.tenant_id, body.keys)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── AI screening settings (per tenant) ─────────────────────────────────────


@router.get("/ai-screening", response_model=AiScreeningSettings)
async def get_ai_screening_settings(
    tenant_id: int | None = Query(None, description="Required for superadmin"),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.SETTINGS_VIEW)),
):
    tid = _resolve_tenant(current_user, tenant_id)
    return await SettingsService(db).get_ai_screening_settings(tid)


@router.patch("/ai-screening", response_model=AiScreeningSettings)
async def update_ai_screening_settings(
    body: AiScreeningSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.SETTINGS_EDIT)),
):
    tid = _resolve_tenant(current_user, body.tenant_id)
    try:
        return await SettingsService(db).update_ai_screening_settings(tid, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
