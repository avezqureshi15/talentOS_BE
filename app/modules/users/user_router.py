from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.users.user_service import UserService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/users", tags=["users"])


@router.get("/benched")
def get_benched_candidates(designation: str = Query(...), db: Session = Depends(get_db)):
    service = UserService(db)
    return service.get_benched_candidates(designation)
