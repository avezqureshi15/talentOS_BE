from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.interviews.interview_schema import (
    InterviewListResponse,
    ScheduleMeetRequest,
    ScheduleMeetResponse,
)
from app.modules.interviews.interview_service import InterviewService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/interviews", tags=["interviews"])


@router.get("", response_model=InterviewListResponse)
def list_interviews(
    status_filter: str | None = Query(None, alias="status_filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = InterviewService(db)
    return service.list_interviews(
        status_filter=status_filter, page=page, per_page=per_page,
    )


@router.post("/schedule", response_model=ScheduleMeetResponse, status_code=status.HTTP_201_CREATED)
def schedule_meet(
    data: ScheduleMeetRequest,
    with_gmeet: bool = Query(True),
):
    service = InterviewService()
    return service.schedule_meet(data, with_gmeet=with_gmeet)
