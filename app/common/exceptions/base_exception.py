from app.core.constants import ErrorCode


class BaseAppException(Exception):
    def __init__(self, message: str, code: ErrorCode = ErrorCode.INTERNAL_ERROR, status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> dict[str, str]:
        return {"error": self.message, "code": self.code.value}
