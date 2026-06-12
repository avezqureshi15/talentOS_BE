from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class TodoNotFoundException(BaseAppException):
    def __init__(self, todo_id: int):
        super().__init__(
            message=f"Todo with id {todo_id} not found",
            code=ErrorCode.TODO_NOT_FOUND,
            status_code=404,
        )
