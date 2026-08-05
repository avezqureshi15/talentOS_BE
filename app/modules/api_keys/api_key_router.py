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
from app.modules.tenants.tenant_model import Tenant

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/superadmin/apps",
    tags=["superadmin-apps"],
    dependencies=[Depends(require_permission(Permission.TENANT_EDIT))],
)


def _validate_tenant(db: Session, tenant_id: int | None) -> int | None:
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Superadmin must provide a tenant_id")
    tenant = db.execute(
        Tenant.__table__.select().where(Tenant.id == tenant_id)
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant_id


@router.post("", response_model=ApiKeyCreatedResponse)
def create_app(
    body: CreateAppRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.TENANT_EDIT)),
):
    tenant_id = _validate_tenant(db, body.tenant_id)
    service = ApiKeyService(db)
    result = service.create_app(
        name=body.name,
        description=body.description,
        created_by_user_id=None if current_user.is_api_key else current_user.id,
        tenant_id=tenant_id,
        expires_at=body.expires_at,
    )
    return result


@router.get("", response_model=ApiKeyListResponse)
def list_apps(
    q: str | None = Query(None, description="Search by app name"),
    tenant_id: int | None = Query(None, description="Filter by tenant"),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.TENANT_EDIT)),
):
    service = ApiKeyService(db)
    return service.list_apps(page=page, per_page=per_page, search=q, tenant_id=tenant_id)


@router.get("/{app_id}", response_model=ApiKeyDetailResponse)
def get_app(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.TENANT_EDIT)),
):
    service = ApiKeyService(db)
    result = service.get_app(app_id)
    if not result:
        raise HTTPException(status_code=404, detail="App not found")
    return result


@router.patch("/{app_id}", response_model=ApiKeyResponse)
def update_app(
    app_id: int,
    body: UpdateAppRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.TENANT_EDIT)),
):
    service = ApiKeyService(db)
    result = service.update_app(
        app_id,
        name=body.name,
        description=body.description,
        expires_at=body.expires_at,
    )
    if not result:
        raise HTTPException(status_code=404, detail="App not found")
    return result


@router.delete("/{app_id}")
def revoke_app(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.TENANT_EDIT)),
):
    """Soft-delete: sets `is_active=false`. The row and its permission grants are preserved for audit."""
    service = ApiKeyService(db)
    ok = service.revoke_app(app_id)
    if not ok:
        raise HTTPException(status_code=404, detail="App not found")
    return {"message": "App revoked successfully"}


@router.post("/{app_id}/rotate", response_model=ApiKeyCreatedResponse)
def rotate_key(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.TENANT_EDIT)),
):
    service = ApiKeyService(db)
    result = service.rotate_key(app_id)
    if not result:
        raise HTTPException(status_code=404, detail="App not found")
    return result


@router.put("/{app_id}/permissions", response_model=ApiKeyDetailResponse)
def update_app_permissions(
    app_id: int,
    body: UpdatePermissionsRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.TENANT_EDIT)),
):
    service = ApiKeyService(db)
    result = service.update_permissions(app_id, body.permission_codes)
    if not result:
        raise HTTPException(status_code=404, detail="App not found")
    return result
