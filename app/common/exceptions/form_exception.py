from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class FormNotFoundException(BaseAppException):
    def __init__(self, form_id: str):
        super().__init__(
            message=f"Form with id {form_id} not found",
            code=ErrorCode.FORM_NOT_FOUND,
            status_code=404,
        )


class FormValidationException(BaseAppException):
    def __init__(self, message: str, code: ErrorCode = ErrorCode.VALIDATION_ERROR):
        super().__init__(
            message=message,
            code=code,
            status_code=400,
        )
