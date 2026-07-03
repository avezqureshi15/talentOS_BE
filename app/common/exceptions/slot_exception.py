from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class SlotNotFoundException(BaseAppException):
    def __init__(self, slot_id: str):
        super().__init__(
            message=f"Slot with id {slot_id} not found",
            code=ErrorCode.SLOT_NOT_FOUND,
            status_code=404,
        )


class SlotBookedException(BaseAppException):
    def __init__(self, message: str = "Cannot modify a booked slot"):
        super().__init__(
            message=message,
            code=ErrorCode.SLOT_BOOKED,
            status_code=409,
        )


class SlotInvalidStatusException(BaseAppException):
    def __init__(self, message: str = "Invalid slot status transition"):
        super().__init__(
            message=message,
            code=ErrorCode.SLOT_INVALID_STATUS,
            status_code=400,
        )


class EmployeeNotFoundException(BaseAppException):
    def __init__(self, emp_id: str):
        super().__init__(
            message=f"Employee with emp_id {emp_id} not found",
            code=ErrorCode.USER_NOT_FOUND,
            status_code=404,
        )
