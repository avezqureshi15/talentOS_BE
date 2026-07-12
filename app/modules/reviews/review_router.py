import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.reviews.review_schema import ReviewCreate, ReviewResponse, ReviewUpdateByRound
from app.modules.reviews.review_service import ReviewService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/reviews", tags=["reviews"])


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(data: ReviewCreate, db: Session = Depends(get_db)):
    service = ReviewService(db)
    return service.create_review(data)


@router.get("/round/{round_id}", response_model=list[ReviewResponse])
def get_reviews_by_round(round_id: str, db: Session = Depends(get_db)):
    service = ReviewService(db)
    return service.get_reviews_by_round(round_id)


@router.put("/round/{round_id}", response_model=ReviewResponse)
def update_review_by_round(round_id: uuid.UUID, data: ReviewUpdateByRound, db: Session = Depends(get_db)):
    service = ReviewService(db)
    return service.upsert_review(round_id, data)
