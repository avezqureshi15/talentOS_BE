import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.events.event_service import EventService
from app.modules.interviews.interview_schema import (
    BookInterviewRequest,
    CancelInterviewResponse,
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

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/interviews", tags=["interviews"])

@router.get("", response_model=InterviewListResponse)
def list_interviews(
    status_filter: str | None = Query(None, alias="status_filter"),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = InterviewService(db)
    return service.list_interviews(
        status_filter=status_filter, search=search, page=page, per_page=per_page,
    )

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
        interviewer_ids=data.interviewer_ids,
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
