from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class DesignationNotFoundException(BaseAppException):
    def __init__(self, name: str):
        super().__init__(
            message=f"Designation '{name}' not found",
            code=ErrorCode.DESIGNATION_NOT_FOUND,
            status_code=404,
        )
