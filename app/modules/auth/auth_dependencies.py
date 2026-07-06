from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.auth_schema import UserInfo
from app.modules.auth.auth_service import AuthService


def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
) -> UserInfo:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    service = AuthService(db)
    try:
        return service.get_current_user(token)
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail=str(exc))
