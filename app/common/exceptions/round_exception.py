from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class RoundNotFoundException(BaseAppException):
    def __init__(self, round_id: str):
        super().__init__(
            message=f"Round with id {round_id} not found",
            code=ErrorCode.ROUND_NOT_FOUND,
            status_code=404,
        )
