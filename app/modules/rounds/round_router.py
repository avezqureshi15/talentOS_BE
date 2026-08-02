from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.modules.rounds.round_schema import (
    PaginatedRoundResponse,
    RoundCreate,
    RoundDetailResponse,
    RoundResponse,
    RoundVerdictRequest,
)
from app.modules.rounds.round_service import RoundService
from app.modules.reviews.review_schema import ReviewUpdateByRound
from app.modules.reviews.review_service import ReviewService
from app.modules.evaluations.evaluation_model import Candidate

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/rounds", tags=["rounds"])


@router.post("", response_model=RoundResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(Permission.APPLICATION_VIEW))])
def create_round(data: RoundCreate, db: Session = Depends(get_db)):
    service = RoundService(db)
    return service.create_round(data)


@router.get("", response_model=PaginatedRoundResponse, dependencies=[Depends(require_permission(Permission.APPLICATION_VIEW))])
def list_rounds(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    candidate_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    service = RoundService(db)
    return service.get_rounds_paginated(page=page, per_page=per_page, search=search, candidate_id=candidate_id)


@router.get("/{round_id}", response_model=RoundDetailResponse)
def get_round_by_id(round_id: UUID, db: Session = Depends(get_db)):
    service = RoundService(db)
    result = service.get_round_detail(round_id)
    if not result:
        raise HTTPException(status_code=404, detail="Round not found")
    return result


@router.get("/candidate/{candidate_id}", response_model=list[RoundResponse], dependencies=[Depends(require_permission(Permission.APPLICATION_VIEW))])
def get_rounds_by_candidate(candidate_id: int, db: Session = Depends(get_db)):
    service = RoundService(db)
    return service.get_rounds_by_candidate(candidate_id)


def _guard_candidate_finalized(candidate_id: int, db: Session) -> None:
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if candidate and candidate.final_verdict is not None:
        raise HTTPException(
            status_code=400,
            detail=f"Candidate already finalized with verdict: {candidate.final_verdict}",
        )


@router.post("/{round_id}/shortlist", dependencies=[Depends(require_permission(Permission.APPLICATION_VIEW))])
def shortlist_round(round_id: UUID, data: RoundVerdictRequest, db: Session = Depends(get_db)):
    from app.modules.rounds.round_model import Round as _Round
    round_obj = db.query(_Round).filter(_Round.id == round_id).first()
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")
    if not round_obj.candidate_id:
        raise HTTPException(status_code=400, detail="Round has no candidate")

    _guard_candidate_finalized(round_obj.candidate_id, db)

    review_data = ReviewUpdateByRound(entity_type="hr", reviews={"remark": data.remark}, verdict=data.verdict)
    review_svc = ReviewService(db)
    review_svc.upsert_review(round_id, review_data)

    from app.modules.applications.application_service import ApplicationService
    ApplicationService(db).handle_hr_verdict(round_id, data.verdict)

    from app.modules.events.event_schema import EventCreate
    from app.modules.events.event_service import EventService
    is_selected = data.verdict == "shortlisted"
    EventService(db).create_event(EventCreate(
        entity_type="CANDIDATE",
        entity_id=str(round_obj.candidate_id),
        event_name="HR Shortlisted Candidate" if is_selected else "HR Rejected Candidate",
        state_code="HR_SHORTLISTED" if is_selected else "HR_REJECTED",
        actor_type="HR",
        candidate_id=round_obj.candidate_id,
        event_metadata={
            "round_id": str(round_id),
            "round_name": round_obj.name,
            "source": "round_action",
        },
    ))

    return RoundResponse.model_validate(
        db.query(_Round).filter(_Round.id == round_id).first()
    )


@router.post("/{round_id}/reject", dependencies=[Depends(require_permission(Permission.APPLICATION_VIEW))])
def reject_round(round_id: UUID, data: RoundVerdictRequest, db: Session = Depends(get_db)):
    return shortlist_round(round_id, RoundVerdictRequest(verdict="rejected", remark=data.remark), db)
