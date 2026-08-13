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
        # A key's stored role (account_admin / job_owner / recruiter / reviewer)
        # drives its identity; legacy keys without a role keep the previous
        # behavior (account_admin for tenant-scoped, superadmin otherwise).
        role = api_key.role or ("account_admin" if is_tenant_scoped else "superadmin")
        return UserInfo(
            id=-api_key.id,
            email=api_key.name,
            name=api_key.name,
            role=role,
            tenant_id=api_key.tenant_id,
            auth_provider="api_key",
            is_active=True,
            permissions=permissions,
            is_api_key=True,
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


def _require_superadmin(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user


RequireSuperAdmin = _require_superadmin


def require_human_user(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """Reject requests authenticated via an API key.

    Use this on endpoints that write rows with FKs to `users.id` or that
    otherwise only make sense for a real human session (invites, chats,
    hiring-request ownership). API keys still authenticate for every other
    endpoint they hold permissions for — this dependency only guards the
    specific handlers it decorates. It never mutates the key itself.
    """
    if current_user.is_api_key:
        raise HTTPException(
            status_code=403,
            detail="This endpoint is not available for API-key callers.",
        )
    return current_user
