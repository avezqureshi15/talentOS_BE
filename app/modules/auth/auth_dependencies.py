from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.auth_schema import UserInfo


def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
) -> UserInfo:
    from app.modules.auth.auth_service import AuthService

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header")

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
