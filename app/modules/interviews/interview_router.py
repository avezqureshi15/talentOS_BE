from fastapi import APIRouter, Query, status

from app.core.config import settings
from app.modules.interviews.interview_schema import ScheduleMeetRequest, ScheduleMeetResponse
from app.modules.interviews.interview_service import InterviewService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/interviews", tags=["interviews"])


@router.post("/schedule", response_model=ScheduleMeetResponse, status_code=status.HTTP_201_CREATED)
def schedule_meet(
    data: ScheduleMeetRequest,
    with_gmeet: bool = Query(True),
):
    service = InterviewService()
    return service.schedule_meet(data, with_gmeet=with_gmeet)
