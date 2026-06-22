from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class EvaluationNotFoundException(BaseAppException):
    def __init__(self, application_id: str):
        super().__init__(
            message=f"Evaluation for application {application_id} not found",
            code=ErrorCode.EVALUATION_NOT_FOUND,
            status_code=404,
        )


class WebhookUnauthorizedException(BaseAppException):
    def __init__(self, message: str = "Invalid or missing webhook secret"):
        super().__init__(
            message=message,
            code=ErrorCode.WEBHOOK_UNAUTHORIZED,
            status_code=401,
        )


class WebhookInvalidPayloadException(BaseAppException):
    def __init__(self, message: str = "Invalid webhook payload"):
        super().__init__(
            message=message,
            code=ErrorCode.WEBHOOK_INVALID_PAYLOAD,
            status_code=400,
        )


class QueuePublishException(BaseAppException):
    def __init__(self, message: str = "Failed to publish evaluation task to queue"):
        super().__init__(
            message=message,
            code=ErrorCode.QUEUE_PUBLISH_FAILED,
            status_code=502,
        )
