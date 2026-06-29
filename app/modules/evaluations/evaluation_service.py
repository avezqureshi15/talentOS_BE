import hmac
from datetime import datetime, timezone

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
    EvaluationMessage,
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

    def ingest(self, payload: SupabaseWebhookPayload) -> IngestResponse:
        """Validate, deduplicate, persist QUEUED, and publish to Kafka."""
        if payload.type != _EXPECTED_EVENT or payload.table != _EXPECTED_TABLE:
            raise WebhookInvalidPayloadException(
                f"Expected {_EXPECTED_EVENT} on {_EXPECTED_TABLE}, got {payload.type} on {payload.table}"
            )

        record = payload.record
        application_id = str(record.id)
        if not record.job_id:
            raise WebhookInvalidPayloadException("Missing job_id in webhook record")

        logger.info("Ingesting application: application_id=%s | job_id=%s", application_id, record.job_id)

        # Idempotency — Supabase webhooks are at-least-once.
        existing = self.repository.get_by_application_id(application_id)
        if existing is not None:
            logger.info("Duplicate application ignored: application_id=%s", application_id)
            return IngestResponse(
                status="duplicate",
                application_id=application_id,
                detail="Application already ingested",
            )

        # Persist QUEUED first — durable truth even if the publish fails.
        evaluation = self.repository.create_queued(
            application_id=application_id,
            job_id=str(record.job_id),
            candidate_name=record.name,
            candidate_email=record.email,
            candidate_phone=record.phone,
            cover_letter=record.cover_letter,
            resume_url=record.resume_url,
        )

        message = EvaluationMessage(
            application_id=application_id,
            job_id=str(record.job_id),
            resume_url=record.resume_url,
            candidate_name=record.name,
            candidate_email=record.email,
            enqueued_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            # Key by application_id (not job_id) so a burst of applications for a
            # single newly-posted job is spread evenly across all partitions and
            # processed in parallel by every worker, instead of serialising on one.
            publish(
                topic=settings.KAFKA_TOPIC_EVALUATION,
                key=application_id,
                value=message.model_dump_json(),
            )
        except Exception as exc:  # noqa: BLE001
            # Row stays QUEUED so a webhook re-delivery (or a manual replay)
            # can re-publish it without creating a duplicate.
            logger.error("Failed to publish to Kafka: application_id=%s | %s", application_id, str(exc))
            raise QueuePublishException() from exc

        logger.info("Application queued: application_id=%s", application_id)
        return IngestResponse(status="queued", application_id=application_id)

    def get_by_job(self, job_id: str, status: str | None = None) -> list[EvaluationResponse]:
        evaluations = self.repository.get_by_job(job_id, status=status)
        return [EvaluationResponse.model_validate(e) for e in evaluations]
