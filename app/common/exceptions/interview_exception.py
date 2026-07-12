from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class InterviewNotFoundException(BaseAppException):
    def __init__(self, interview_id: str):
        super().__init__(
            message=f"Interview with id {interview_id} not found",
            code=ErrorCode.INTERVIEW_NOT_FOUND,
            status_code=404,
        )
