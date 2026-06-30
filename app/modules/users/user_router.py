from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.db.session import get_db
from app.modules.users.user_schema import PaginatedUserResponse, UserResponse
from app.modules.users.user_service import UserService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/users", tags=["users"])


@router.get("/benched")
def get_benched_candidates(designation: str = Query(...), db: Session = Depends(get_db)):
    service = UserService(db)
    return service.get_benched_candidates(designation)


@router.get("/{emp_id}", response_model=UserResponse | None)
def get_user_by_emp_id(emp_id: str, db: Session = Depends(get_db)):
    service = UserService(db)
    return service.get_user_by_emp_id(emp_id)


@router.get("/", response_model=PaginatedUserResponse)
def list_users(
    q: str | None = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
):
    service = UserService(db)
    return service.search_users(query=q, page=page, per_page=per_page)
