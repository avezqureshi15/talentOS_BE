from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class CronTransientError(BaseAppException):
    """Retryable error in a cron job — the job will re-attempt with backoff."""

    def __init__(self, message: str = "Transient cron job error, will retry"):
        super().__init__(
            message=message,
            code=ErrorCode.CRON_JOB_FAILED,
            status_code=0,
        )
