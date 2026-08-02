from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class NotificationNotFoundException(BaseAppException):
    def __init__(self, notification_id: str):
        super().__init__(
            message=f"Notification with id {notification_id} not found",
            code=ErrorCode.NOTIFICATION_NOT_FOUND,
            status_code=404,
        )
