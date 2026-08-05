from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.config import settings
from app.core.constants import DEFAULT_PAGE_SIZE
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.api_keys.api_key_schema import (
    ApiKeyCreatedResponse,
    ApiKeyDetailResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
    CreateAppRequest,
    UpdateAppRequest,
    UpdatePermissionsRequest,
)
from app.modules.api_keys.api_key_service import ApiKeyService
from app.modules.auth.auth_schema import UserInfo

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/admin/apps",
    tags=["admin-apps"],
    dependencies=[Depends(require_permission(Permission.API_KEY_MANAGE))],
)


def _own_tenant_id(current_user: UserInfo) -> int:
    if current_user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Admin user has no tenant")
    return current_user.tenant_id


@router.post("", response_model=ApiKeyCreatedResponse)
def create_app(
    body: CreateAppRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.API_KEY_MANAGE)),
):
    service = ApiKeyService(db)
    result = service.create_app(
        name=body.name,
        description=body.description,
        created_by_user_id=None if current_user.is_api_key else current_user.id,
        tenant_id=_own_tenant_id(current_user),
        expires_at=body.expires_at,
    )
    return result


@router.get("", response_model=ApiKeyListResponse)
def list_apps(
    q: str | None = Query(None, description="Search by app name"),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.API_KEY_MANAGE)),
):
    service = ApiKeyService(db)
    return service.list_apps(page=page, per_page=per_page, search=q, tenant_id=_own_tenant_id(current_user))


@router.get("/{app_id}", response_model=ApiKeyDetailResponse)
def get_app(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.API_KEY_MANAGE)),
):
    service = ApiKeyService(db)
    result = service.get_app(app_id, tenant_id=_own_tenant_id(current_user))
    if not result:
        raise HTTPException(status_code=404, detail="App not found")
    return result


@router.patch("/{app_id}", response_model=ApiKeyResponse)
def update_app(
    app_id: int,
    body: UpdateAppRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.API_KEY_MANAGE)),
):
    service = ApiKeyService(db)
    result = service.update_app(
        app_id,
        name=body.name,
        description=body.description,
        tenant_id=_own_tenant_id(current_user),
        expires_at=body.expires_at,
    )
    if not result:
        raise HTTPException(status_code=404, detail="App not found")
    return result


@router.delete("/{app_id}")
def revoke_app(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.API_KEY_MANAGE)),
):
    """Soft-delete: sets `is_active=false`. The row and its permission grants are preserved for audit."""
    service = ApiKeyService(db)
    ok = service.revoke_app(app_id, tenant_id=_own_tenant_id(current_user))
    if not ok:
        raise HTTPException(status_code=404, detail="App not found")
    return {"message": "App revoked successfully"}


@router.post("/{app_id}/rotate", response_model=ApiKeyCreatedResponse)
def rotate_key(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.API_KEY_MANAGE)),
):
    service = ApiKeyService(db)
    result = service.rotate_key(app_id, tenant_id=_own_tenant_id(current_user))
    if not result:
        raise HTTPException(status_code=404, detail="App not found")
    return result


@router.put("/{app_id}/permissions", response_model=ApiKeyDetailResponse)
def update_app_permissions(
    app_id: int,
    body: UpdatePermissionsRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.API_KEY_MANAGE)),
):
    service = ApiKeyService(db)
    result = service.update_permissions(app_id, body.permission_codes, tenant_id=_own_tenant_id(current_user))
    if not result:
        raise HTTPException(status_code=404, detail="App not found")
    return result
