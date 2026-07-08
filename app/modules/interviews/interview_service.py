import os

from googleapiclient.errors import HttpError

from app.common.exceptions.calendar_exception import (
    CalendarApiFailedException,
    CalendarNotConfiguredException,
)
from app.common.services.google_calendar_service import GoogleCalendarService
from app.core.config import settings
from app.core.logger import get_logger
from app.modules.interviews.interview_schema import ScheduleMeetRequest, ScheduleMeetResponse

logger = get_logger(__name__)


class InterviewService:
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
            result = calendar.create_meet(
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

        return ScheduleMeetResponse(**result)
