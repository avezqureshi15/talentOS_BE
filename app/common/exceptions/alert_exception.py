from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class AlertNotFoundException(BaseAppException):
    def __init__(self, alert_id: str):
        super().__init__(
            message=f"Alert with id {alert_id} not found",
            code=ErrorCode.ALERT_NOT_FOUND,
            status_code=404,
        )
