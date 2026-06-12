from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class UserNotFoundException(BaseAppException):
    def __init__(self, user_id: int):
        super().__init__(
            message=f"User with id {user_id} not found",
            code=ErrorCode.USER_NOT_FOUND,
            status_code=404,
        )
