import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.modules.events.event_schema import EventCreate
from app.modules.events.event_service import EventService
from app.modules.reviews.review_schema import ReviewCreate, ReviewResponse, ReviewUpdateByRound
from app.modules.reviews.review_service import ReviewService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/reviews", tags=["reviews"])


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(data: ReviewCreate, db: Session = Depends(get_db)):
    service = ReviewService(db)
    return service.create_review(data)


@router.get("/round/{round_id}", response_model=list[ReviewResponse], dependencies=[Depends(require_permission(Permission.REVIEW_VIEW_ALL))])
def get_reviews_by_round(round_id: str, db: Session = Depends(get_db)):
    service = ReviewService(db)
    return service.get_reviews_by_round(round_id)


@router.put("/round/{round_id}", response_model=ReviewResponse)
def update_review_by_round(round_id: uuid.UUID, data: ReviewUpdateByRound, db: Session = Depends(get_db)):
    service = ReviewService(db)
    result = service.upsert_review(round_id, data)

    if data.entity_type == "hr":
        from app.modules.applications.application_service import ApplicationService

        ApplicationService(db).handle_hr_verdict(round_id, data.verdict)
        if data.verdict in ("shortlisted", "rejected"):
            from app.modules.rounds.round_model import Round
            round_obj = db.query(Round).filter(Round.id == round_id).first()
            candidate_id = round_obj.candidate_id if round_obj else None
            if candidate_id:
                is_selected = data.verdict == "shortlisted"
                EventService(db).create_event(EventCreate(
                    entity_type="CANDIDATE",
                    entity_id=str(candidate_id),
                    event_name="HR Shortlisted Candidate" if is_selected else "HR Rejected Candidate",
                    state_code="HR_SHORTLISTED" if is_selected else "HR_REJECTED",
                    actor_type="HR",
                    candidate_id=candidate_id,
                    event_metadata={"round_id": str(round_id), "round_name": round_obj.name} if round_obj else None,
                ))

    return result
