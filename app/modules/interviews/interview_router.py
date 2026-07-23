import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.auth.auth_dependencies import RequireHr
from app.modules.events.event_service import EventService
from fastapi.responses import JSONResponse

from app.modules.interviews.interview_schema import (
    BookInterviewRequest,
    CancelInterviewResponse,
    InterviewListItem,
    InterviewListResponse,
    RescheduleInterviewRequest,
    ScheduleInterviewRequest,
    ScheduleInterviewResponse,
    ScheduleMeetRequest,
    ScheduleMeetResponse,
)
from app.modules.interviews.interview_booking_service import BookingService
from app.modules.interviews.interview_schedule_service import InterviewScheduleService
from app.modules.interviews.interview_service import InterviewService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/interviews", tags=["interviews"], dependencies=[Depends(RequireHr)])

@router.get("", response_model=InterviewListResponse)
def list_interviews(
    status_filter: str | None = Query(None, alias="status_filter"),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    candidate_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    service = InterviewService(db)
    return service.list_interviews(
        status_filter=status_filter, search=search, page=page, per_page=per_page, candidate_id=candidate_id,
    )

@router.get("/{interview_id}")
def get_interview_detail(
    interview_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = InterviewService(db)
    result = service.get_interview_by_id(interview_id)
    if not result:
        return JSONResponse(status_code=404, content={"success": False, "error": "Interview not found"})
    return {"success": True, "data": result}

@router.post("/schedule", response_model=ScheduleMeetResponse, status_code=status.HTTP_201_CREATED)
def schedule_meet(
    data: ScheduleMeetRequest,
    with_gmeet: bool = Query(True),
):
    service = InterviewService()
    return service.schedule_meet(data, with_gmeet=with_gmeet)

@router.post("/scheduling", response_model=ScheduleInterviewResponse, status_code=status.HTTP_201_CREATED)
def schedule_interview(
    data: ScheduleInterviewRequest,
    db: Session = Depends(get_db),
):
    svc = InterviewScheduleService(db, event_service=EventService(db))
    return svc.schedule_interview(
        round_id=uuid.UUID(data.round_id),
        slot_id=uuid.UUID(data.slot_id),
    )

@router.patch("/scheduling/{interview_id}/reschedule", response_model=ScheduleInterviewResponse)
def reschedule_interview(
    interview_id: uuid.UUID,
    data: RescheduleInterviewRequest,
    db: Session = Depends(get_db),
):
    svc = InterviewScheduleService(db, event_service=EventService(db))
    return svc.reschedule_interview(
        interview_id=interview_id,
        new_slot_id=uuid.UUID(data.slot_id),
    )

@router.patch("/scheduling/{interview_id}/cancel", response_model=CancelInterviewResponse)
def cancel_interview(
    interview_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    svc = InterviewScheduleService(db, event_service=EventService(db))
    return svc.cancel_interview(interview_id=interview_id)


@router.post("/booking", response_model=ScheduleInterviewResponse, status_code=status.HTTP_201_CREATED)
def book_interview(data: BookInterviewRequest, db: Session = Depends(get_db)):
    return BookingService(db, event_service=EventService(db)).book_interview(data)
