from app.common.exceptions.calendar_exception import CalendarNotConfiguredException
from app.common.services.google_calendar_service import GoogleCalendarService
from app.core.config import settings


def get_calendar_service() -> GoogleCalendarService:
    path = settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip()
    email = settings.GOOGLE_IMPERSONATION_EMAIL.strip()
    if not (path and email):
        raise CalendarNotConfiguredException()
    return GoogleCalendarService(
        service_account_path=path,
        impersonation_email=email,
        timezone=settings.GOOGLE_CALENDAR_TIMEZONE,
    )
