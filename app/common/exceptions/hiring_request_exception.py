from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class HiringRequestNotFoundException(BaseAppException):
    def __init__(self, hiring_request_id: str):
        super().__init__(
            message=f"Hiring request with id {hiring_request_id} not found",
            code=ErrorCode.HIRING_REQUEST_NOT_FOUND,
            status_code=404,
        )


class HiringRequestNotCreatedException(BaseAppException):
    def __init__(self, message: str = "Failed to create hiring request"):
        super().__init__(
            message=message,
            code=ErrorCode.HIRING_REQUEST_NOT_CREATED,
            status_code=500,
        )
