from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class JobNotFoundException(BaseAppException):
    def __init__(self, job_id: str | None):
        super().__init__(
            message=f"Job listing with id {job_id} not found",
            code=ErrorCode.JOB_NOT_FOUND,
            status_code=404,
        )


class JobNotCreatedException(BaseAppException):
    def __init__(self, message: str = "Failed to create job listing"):
        super().__init__(
            message=message,
            code=ErrorCode.INTERNAL_ERROR,
            status_code=500,
        )
