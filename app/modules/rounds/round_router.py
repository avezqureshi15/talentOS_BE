from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.rounds.round_schema import RoundCreate, RoundResponse
from app.modules.rounds.round_service import RoundService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/rounds", tags=["rounds"])


@router.post("", response_model=RoundResponse, status_code=status.HTTP_201_CREATED)
def create_round(data: RoundCreate, db: Session = Depends(get_db)):
    service = RoundService(db)
    return service.create_round(data)
