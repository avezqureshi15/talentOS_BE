from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class EventNotFoundException(BaseAppException):
    def __init__(self, event_id: str):
        super().__init__(
            message=f"Event with id {event_id} not found",
            code=ErrorCode.EVENT_NOT_FOUND,
            status_code=404,
        )
