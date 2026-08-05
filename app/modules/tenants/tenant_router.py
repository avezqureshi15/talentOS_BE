from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import DEFAULT_PAGE_SIZE
from app.core.logger import get_logger
from app.db.session import get_db
from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.modules.auth.auth_schema import UserInfo
from app.modules.tenants.tenant_service import TenantService, TenantError
from app.modules.tenants.tenant_schema import (
    CreateTenantRequest,
    UpdateTenantRequest,
    TenantResponse,
    PaginatedTenantResponse,
    TenantAdminDetails,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/superadmin/tenants",
    tags=["superadmin-tenants"],
    dependencies=[Depends(require_permission(Permission.TENANT_VIEW))],
)


@router.post("", response_model=TenantAdminDetails)
def create_tenant(
    body: CreateTenantRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.TENANT_EDIT)),
):
    if current_user.is_api_key:
        raise HTTPException(status_code=403, detail="Tenants cannot be created by an API key")
    service = TenantService(db)
    try:
        return service.create_tenant(
            org_name=body.org_name,
            admin_name=body.admin_name,
            admin_email=body.admin_email,
            invited_by_user_id=current_user.id,
        )
    except TenantError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("", response_model=PaginatedTenantResponse)
def list_tenants(
    q: str | None = Query(None, description="Search by name or slug"),
    status: str | None = Query(None, description="Filter: pending, approved, rejected, active, suspended"),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.TENANT_VIEW)),
):
    service = TenantService(db)
    return service.list_tenants(page=page, per_page=per_page, search=q, status_filter=status)


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.TENANT_VIEW)),
):
    service = TenantService(db)
    try:
        return service.get_tenant(tenant_id)
    except TenantError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.patch("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: int,
    body: UpdateTenantRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.TENANT_VIEW)),
):
    service = TenantService(db)
    data = body.model_dump(exclude_none=True)
    try:
        return service.update_tenant(tenant_id, data)
    except TenantError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/{tenant_id}")
def delete_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.TENANT_VIEW)),
):
    service = TenantService(db)
    try:
        service.delete_tenant(tenant_id)
        return {"message": "Tenant suspended successfully"}
    except TenantError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
