from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import get_logger
from app.db.session import get_db
from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.modules.auth.auth_schema import UserInfo
from app.modules.tenants.tenant_service import TenantService, TenantError
from app.modules.tenants.tenant_schema import TenantResponse, UpdateOrganizationRequest

logger = get_logger(__name__)

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/admin/organization",
    tags=["admin-organization"],
    dependencies=[Depends(require_permission(Permission.SETTINGS_VIEW))],
)


@router.get("", response_model=TenantResponse)
def get_organization(
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.SETTINGS_VIEW)),
):
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Admin user has no tenant")

    service = TenantService(db)
    try:
        return service.get_tenant(tenant_id)
    except TenantError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.patch("", response_model=TenantResponse)
def update_organization(
    body: UpdateOrganizationRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.SETTINGS_EDIT)),
):
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Admin user has no tenant")

    service = TenantService(db)
    tenant = service.repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    data = body.model_dump(exclude_unset=True)
    for key in ("phone", "address_line1"):
        if key in data and isinstance(data[key], str):
            data[key] = data[key].strip() or None

    final_phone = data["phone"] if "phone" in data else tenant.phone
    final_address = data["address_line1"] if "address_line1" in data else tenant.address_line1
    if not (final_phone or "").strip():
        raise HTTPException(status_code=422, detail="Phone is required")
    if not (final_address or "").strip():
        raise HTTPException(status_code=422, detail="Address Line 1 is required")

    try:
        return service.update_tenant(tenant_id, data)
    except TenantError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
