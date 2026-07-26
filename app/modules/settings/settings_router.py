from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.db.session import get_db
from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.modules.auth.auth_schema import UserInfo
from app.modules.settings.settings_schema import SettingsResponse, UpdateSettingsRequest
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
