from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.rounds.round_schema import RoundCreate, RoundDetailResponse, RoundResponse
from app.modules.rounds.round_service import RoundService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/rounds", tags=["rounds"])


@router.post("", response_model=RoundResponse, status_code=status.HTTP_201_CREATED)
def create_round(data: RoundCreate, db: Session = Depends(get_db)):
    service = RoundService(db)
    return service.create_round(data)


@router.get("/{round_id}", response_model=RoundDetailResponse)
def get_round_by_id(round_id: UUID, db: Session = Depends(get_db)):
    service = RoundService(db)
    result = service.get_round_detail(round_id)
    if not result:
        raise HTTPException(status_code=404, detail="Round not found")
    return result


@router.get("/candidate/{candidate_id}", response_model=list[RoundResponse])
def get_rounds_by_candidate(candidate_id: int, db: Session = Depends(get_db)):
    service = RoundService(db)
    return service.get_rounds_by_candidate(candidate_id)
