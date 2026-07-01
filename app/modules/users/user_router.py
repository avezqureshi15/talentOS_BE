from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.users.user_schema import PaginatedUserResponse, UserResponse
from app.modules.users.user_service import UserService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/users", tags=["users"])


@router.get("/")
def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    q: str | None = Query(None, description="Search query"),
    db: Session = Depends(get_db),
) -> PaginatedUserResponse:
    service = UserService(db)
    return service.list_users(page, per_page, q)


@router.get("/{emp_id}")
def get_user_by_emp_id(emp_id: str, db: Session = Depends(get_db)) -> UserResponse | None:
    service = UserService(db)
    user = service.get_user_by_emp_id(emp_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/benched")
def get_benched_candidates(designation: str = Query(...), db: Session = Depends(get_db)):
    service = UserService(db)
    return service.get_benched_candidates(designation)
