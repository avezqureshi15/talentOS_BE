from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class ReviewNotFoundException(BaseAppException):
    def __init__(self, review_id: str):
        super().__init__(
            message=f"Review with id {review_id} not found",
            code=ErrorCode.REVIEW_NOT_FOUND,
            status_code=404,
        )
