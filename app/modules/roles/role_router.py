from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.config import settings
from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, Permission
from app.db.session import get_db
from app.modules.roles.role_schema import (
    CreateRoleRequest,
    PermissionsListResponse,
    RoleListResponse,
    RoleResponse,
    UpdateRolePermissionsRequest,
)
from app.modules.roles.role_service import RoleService

RESERVED_ROLE_NAMES = {"admin", "hr", "viewer"}

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/admin/roles",
    tags=["admin-roles"],
    dependencies=[Depends(require_permission(Permission.USER_MANAGE))],
)


@router.get("", response_model=RoleListResponse)
def list_roles(db: Session = Depends(get_db)):
    service = RoleService(db)
    roles = service.list_roles()
    return RoleListResponse(roles=roles)


@router.get("/permissions", response_model=PermissionsListResponse)
def list_all_permissions(db: Session = Depends(get_db)):
    service = RoleService(db)
    perms = service.list_all_permissions()
    return PermissionsListResponse(permissions=perms)


@router.get("/{role_name}", response_model=RoleResponse)
def get_role(role_name: str, db: Session = Depends(get_db)):
    service = RoleService(db)
    result = service.get_role(role_name)
    if not result:
        raise HTTPException(status_code=404, detail="Role not found")
    return result


@router.post("", response_model=RoleResponse, status_code=201)
def create_role(body: CreateRoleRequest, db: Session = Depends(get_db)):
    service = RoleService(db)
    role_name = body.role_name.strip()
    if not role_name:
        raise HTTPException(status_code=400, detail="Role name cannot be empty")
    if role_name in RESERVED_ROLE_NAMES:
        raise HTTPException(status_code=409, detail="Role name is reserved")
    if role_name in DEFAULT_ROLE_PERMISSIONS or service.role_exists(role_name):
        raise HTTPException(status_code=409, detail="Role already exists")
    return service.create_role(role_name, body.description)


@router.delete("/{role_name}", status_code=204)
def delete_role(role_name: str, db: Session = Depends(get_db)):
    service = RoleService(db)
    if role_name in DEFAULT_ROLE_PERMISSIONS:
        raise HTTPException(status_code=400, detail="System roles cannot be deleted")
    if not service.role_exists(role_name):
        raise HTTPException(status_code=404, detail="Role not found")
    service.delete_role(role_name)


@router.put("/{role_name}/permissions", response_model=RoleResponse)
def update_role_permissions(
    role_name: str,
    body: UpdateRolePermissionsRequest,
    db: Session = Depends(get_db),
):
    service = RoleService(db)
    return service.update_role_permissions(role_name, body.permission_codes)
