from fastapi import Depends, HTTPException

from app.core.permissions import Permission
from app.modules.auth.auth_dependencies import get_current_user
from app.modules.auth.auth_schema import UserInfo


def require_permission(*permissions: Permission):
    """FastAPI dependency that checks the current user has ALL listed permissions.

    Usage:
        @router.get("/applications")
        def list_applications(
            _=Depends(require_permission(Permission.APPLICATION_VIEW)),
            ...
        ):
    """
    def checker(current_user: UserInfo = Depends(get_current_user)):
        for p in permissions:
            if p.value not in current_user.permissions:
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing required permission: {p.value}",
                )
        return current_user
    return checker


def require_any_permission(*permissions: Permission):
    """FastAPI dependency that checks the current user has AT LEAST ONE listed permission.

    Usage:
        @router.get("/reports")
        def get_reports(
            _=Depends(require_any_permission(Permission.REPORT_EXPORT)),
            ...
        ):
    """
    def checker(current_user: UserInfo = Depends(get_current_user)):
        if not any(p.value in current_user.permissions for p in permissions):
            raise HTTPException(
                status_code=403,
                detail="Missing required permission",
            )
        return current_user
    return checker
