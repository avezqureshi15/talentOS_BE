import os

from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.common.exceptions.calendar_exception import (
    CalendarApiFailedException,
    CalendarNotConfiguredException,
)
from app.common.schemas.calendar_schema import CalendarEventResponse
from app.common.services.google_calendar_service import GoogleCalendarService
from app.core.config import settings
from app.core.logger import get_logger
from app.modules.interviews.interview_query_repository import InterviewQueryRepository
from app.modules.interviews.interview_schema import (
    InterviewListResponse,
    InterviewListItem,
    InterviewPagination,
    InterviewsData,
    ScheduleMeetRequest,
    ScheduleMeetResponse,
)


logger = get_logger(__name__)


class InterviewService:
    def __init__(self, db: Session | None = None):
        self.db = db
        self.query_repo = InterviewQueryRepository(db) if db else None

    @staticmethod
    def is_configured() -> bool:
        path = settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip()
        email = settings.GOOGLE_IMPERSONATION_EMAIL.strip()
        return bool(path and email and os.path.isfile(path))

    def _get_calendar_service(self) -> GoogleCalendarService:
        if not self.is_configured():
            raise CalendarNotConfiguredException()
        return GoogleCalendarService(
            service_account_path=settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip(),
            impersonation_email=settings.GOOGLE_IMPERSONATION_EMAIL.strip(),
            timezone=settings.GOOGLE_CALENDAR_TIMEZONE,
        )

    def schedule_meet(
        self,
        data: ScheduleMeetRequest,
        *,
        with_gmeet: bool = True,
    ) -> ScheduleMeetResponse:
        calendar = self._get_calendar_service()
        try:
            result: CalendarEventResponse = calendar.create_meet(
                title=data.title,
                start=data.start,
                end=data.end,
                attendees=[str(email) for email in data.attendees],
                description=data.description,
                with_gmeet=with_gmeet,
            )
        except HttpError as exc:
            logger.error("Google Calendar API failed: %s", exc)
            raise CalendarApiFailedException("Failed to create calendar event") from exc
        except Exception as exc:
            logger.error("Unexpected calendar error: %s", exc)
            raise CalendarApiFailedException("Failed to create calendar event") from exc

        return ScheduleMeetResponse(
            event_id=result.event_id,
            meet_link=result.meet_link,
            html_link=result.calendar_link,
            start=data.start,
            end=data.end,
        )

    def list_interviews(
        self,
        status_filter: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> InterviewListResponse:
        if not self.query_repo:
            return InterviewListResponse(data=InterviewsData(
                interviews=[], pagination=InterviewPagination(
                    current_page=page, per_page=per_page, total_records=0, has_more=False,
                ),
            ))
        items, total = self.query_repo.list_paginated(
            status_filter=status_filter, page=page, per_page=per_page,
        )
        interviews = [InterviewListItem(**item) for item in items]
        pagination = InterviewQueryRepository.build_pagination(page, per_page, total)
        return InterviewListResponse(data=InterviewsData(
            interviews=interviews,
            pagination=InterviewPagination(**pagination),
        ))
