from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class CalendarNotConfiguredException(BaseAppException):
    def __init__(self, message: str = "Google Calendar is not configured"):
        super().__init__(
            message=message,
            code=ErrorCode.CALENDAR_NOT_CONFIGURED,
            status_code=503,
        )


class CalendarApiFailedException(BaseAppException):
    def __init__(self, message: str = "Failed to create calendar event"):
        super().__init__(
            message=message,
            code=ErrorCode.CALENDAR_API_FAILED,
            status_code=502,
        )
