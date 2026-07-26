import hmac

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.kafka import publish
from app.core.logger import get_logger
from app.common.exceptions.evaluation_exception import (
    QueuePublishException,
    WebhookInvalidPayloadException,
    WebhookUnauthorizedException,
)
from app.modules.evaluations.evaluation_repository import EvaluationRepository
from app.modules.evaluations.evaluation_schema import (
    AsyncEvaluationMessage,
    EvaluationResponse,
    IngestResponse,
    SupabaseWebhookPayload,
)

logger = get_logger(__name__)

_EXPECTED_TABLE = "job_applications"
_EXPECTED_EVENT = "INSERT"


class EvaluationService:
    def __init__(self, db: Session):
        self.repository = EvaluationRepository(db)

    def verify_webhook_secret(self, provided_secret: str | None) -> None:
        """Constant-time comparison of the shared webhook secret.

        If no secret is configured (local dev), verification is skipped with
        a warning. In production SUPABASE_WEBHOOK_SECRET MUST be set.
        """
        expected = settings.SUPABASE_WEBHOOK_SECRET
        if not expected:
            logger.warning("SUPABASE_WEBHOOK_SECRET not set — skipping webhook verification (dev only)")
            return
        if not provided_secret or not hmac.compare_digest(provided_secret, expected):
            logger.error("Webhook secret mismatch — rejecting request")
            raise WebhookUnauthorizedException()

    def ingest_async(self, payload: SupabaseWebhookPayload) -> IngestResponse:
        """Validate, deduplicate, persist QUEUED, and publish to Kafka for async evaluation."""
        if payload.type != _EXPECTED_EVENT or payload.table != _EXPECTED_TABLE:
            raise WebhookInvalidPayloadException(
                f"Expected {_EXPECTED_EVENT} on {_EXPECTED_TABLE}, got {payload.type} on {payload.table}"
            )

        record = payload.record
        application_id = str(record.id)
        if not record.job_id:
            raise WebhookInvalidPayloadException("Missing job_id in webhook record")

        logger.info("Ingesting async evaluation: application_id=%s | job_id=%s", application_id, record.job_id)

        existing = self.repository.get_by_application_id(application_id)
        if existing is not None:
            logger.info("Duplicate application ignored: application_id=%s", application_id)
            return IngestResponse(
                status="duplicate",
                application_id=application_id,
                detail="Application already ingested",
            )

        self.repository.create_queued(
            application_id=application_id,
            job_id=str(record.job_id),
            candidate_name=record.name,
            candidate_email=record.email,
            candidate_phone=record.phone,
            cover_letter=record.cover_letter,
            resume_url=record.resume_url,
            current_ctc=record.current_ctc,
            expected_ctc=record.expected_ctc,
            location=record.location,
            years_of_experience=record.years_of_experience,
            notice_period=record.notice_period,
            how_did_you_hear=record.how_did_you_hear,
            linkedin_url=record.linkedin_url,
            willing_to_relocate=record.willing_to_relocate,
            candidate_type=record.candidate_type,
        )

        message = AsyncEvaluationMessage(
            application_id=application_id,
            job_id=str(record.job_id),
            candidate_name=record.name,
            candidate_email=record.email,
            candidate_phone=record.phone,
            cover_letter=record.cover_letter,
            resume_url=record.resume_url,
            current_ctc=record.current_ctc,
            expected_ctc=record.expected_ctc,
            location=record.location,
            years_of_experience=record.years_of_experience,
            notice_period=record.notice_period,
            how_did_you_hear=record.how_did_you_hear,
            linkedin_url=record.linkedin_url,
            willing_to_relocate=record.willing_to_relocate,
            candidate_type=record.candidate_type,
        )

        try:
            publish(
                topic=settings.KAFKA_TOPIC_EVALUATION_ASYNC,
                key=application_id,
                value=message.model_dump_json(),
            )
        except Exception as exc:
            logger.error("Failed to publish to Kafka: application_id=%s | %s", application_id, str(exc))
            raise QueuePublishException() from exc

        logger.info("Application queued for async evaluation: application_id=%s", application_id)
        return IngestResponse(status="queued", application_id=application_id)

    def get_by_job(self, job_id: str, status: str | None = None) -> list[EvaluationResponse]:
        evaluations = self.repository.get_by_job(job_id, status=status)
        return [EvaluationResponse.model_validate(e) for e in evaluations]
