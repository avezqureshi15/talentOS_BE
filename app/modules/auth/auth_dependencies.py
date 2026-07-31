from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.auth.auth_schema import UserInfo


def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
) -> UserInfo:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    from app.modules.api_keys.api_key_service import ApiKeyService

    if token.startswith("tal_"):
        api_key = ApiKeyService.validate_api_key(token, db)
        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")

        permissions = ApiKeyService.get_permissions_for_key(api_key.id, db)
        is_tenant_scoped = api_key.tenant_id is not None
        return UserInfo(
            id=-api_key.id,
            email=api_key.name,
            name=api_key.name,
            role="admin" if is_tenant_scoped else "superadmin",
            tenant_id=api_key.tenant_id,
            auth_provider="api_key",
            is_active=True,
            permissions=permissions,
        )

    from app.modules.auth.auth_service import AuthService

    service = AuthService(db)
    try:
        return service.get_current_user(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc))


def require_roles(*roles: str):
    def checker(current_user: UserInfo = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return checker


def _require_hr(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    if current_user.role not in ("hr", "admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user


def _require_admin(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    if current_user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user


def _require_superadmin(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user


RequireHr = _require_hr
RequireAdmin = _require_admin
RequireSuperAdmin = _require_superadmin
