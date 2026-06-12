from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class ApplicationNotFoundException(BaseAppException):
    def __init__(self, application_id: int):
        super().__init__(
            message=f"Application with id {application_id} not found",
            code=ErrorCode.APPLICATION_NOT_FOUND,
            status_code=404,
        )
