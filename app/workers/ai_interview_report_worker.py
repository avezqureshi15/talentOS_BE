"""Async AI interview report transform — Kafka consumer.

Consumes ``ai.interview.report.async`` after ``persist_interview_result``
persists a raw AI interview review, runs the LLM report transform, and
replaces the ``reviews`` JSONB with the rich report (raw copy under ``_raw``).

Delivery semantics: at-least-once.  Transient errors retry with exponential
backoff up to ``INTERVIEW_REPORT_MAX_ATTEMPTS``, then route to the DLQ.
Non-transformable inputs (no transcript, schema-validation failure) are
terminal and keep the raw payload untouched — the offset is committed.

Scalability:
    - Partition-based: worker replicas in the same group share 6 partitions
    - Stateless workers: all state lives in the DB; the message only carries
      the round id and the review row is re-read on each attempt

Usage:
    python -m app.workers.ai_interview_report_worker
"""
from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.core.kafka import ConsumedMessage, consume, publish
from app.core.logger import setup_logging
from app.db.session import SessionLocal
from app.modules.ai.interview_report_schema import InterviewReportMessage
from app.modules.ai.interview_report_transform import (
    TransientTransformError,
    transform_interview_review,
)
from app.modules.reviews.review_schema import ReviewUpdateByRound
from app.modules.reviews.review_service import ReviewService

logger = logging.getLogger(__name__)

_ENTITY = "ai_interview"


def _is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, TransientTransformError):
        return True
    if isinstance(exc, OperationalError):
        return True
    if isinstance(exc, TimeoutError):
        return True
    return False


def _transform_round(round_id: uuid.UUID) -> None:
    """Run one attempt of the transform for a round."""
    db = SessionLocal()
    try:
        service = ReviewService(db)
        review = service.repository.get_by_round_and_entity(round_id, _ENTITY)
        if review is None or not review.reviews:
            logger.info("No %s review found for round_id=%s — skipping", _ENTITY, round_id)
            return

        current = review.reviews
        if "assessment" in current:
            logger.info("round_id=%s already transformed — skipping", round_id)
            return

        transformed = transform_interview_review(current)
        if transformed is None:
            logger.info("Keeping raw review for round_id=%s", round_id)
            return

        service.upsert_review(
            round_id,
            ReviewUpdateByRound(
                entity_type=_ENTITY,
                reviews=transformed,
                verdict=review.verdict,
            ),
        )
        logger.info("Transformed AI interview report for round_id=%s", round_id)
    except TransientTransformError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error transforming round_id=%s", round_id)
        raise TransientTransformError(f"Unexpected error: {exc}") from exc
    finally:
        db.close()


def _route_to_dlq(round_id: uuid.UUID, reason: str) -> None:
    logger.error("Routing round_id=%s to DLQ: %s", round_id, reason)
    try:
        publish(
            topic=settings.KAFKA_TOPIC_INTERVIEW_REPORT_ASYNC_DLQ,
            key=str(round_id),
            value=InterviewReportMessage(round_id=round_id).model_dump_json(),
        )
    except Exception as exc:
        logger.error("Failed to publish to DLQ for round_id=%s: %s", round_id, exc)


def _handler_with_retry(msg: ConsumedMessage) -> None:
    """Deserialize and run the transform with retry + DLQ semantics.

    Catches all exceptions internally so ``consume()`` always commits the
    offset — unless the process crashes, in which case the uncommitted offset
    causes re-delivery (at-least-once).
    """
    message = InterviewReportMessage.model_validate_json(msg.value)
    logger.info(
        "Processing round_id=%s (partition=%s, offset=%s)",
        message.round_id, msg.partition, msg.offset,
    )
    last_error: Exception | None = None
    max_attempts = settings.INTERVIEW_REPORT_MAX_ATTEMPTS

    for attempt in range(1, max_attempts + 1):
        try:
            _transform_round(message.round_id)
            return
        except TransientTransformError as exc:
            last_error = exc
            logger.warning(
                "Transient error (attempt %d/%d) for round_id=%s: %s",
                attempt, max_attempts, message.round_id, exc,
            )
            if attempt < max_attempts:
                delay = min(2 ** attempt, 30)
                logger.info("Retrying in %ds ...", delay)
                time.sleep(delay)
        except Exception as exc:
            last_error = exc
            logger.error(
                "Non-retryable error for round_id=%s: %s",
                message.round_id, exc,
            )
            break

    _route_to_dlq(message.round_id, str(last_error))


def main() -> None:
    setup_logging()
    logger.info(
        "Starting AI interview report worker — topic=%s",
        settings.KAFKA_TOPIC_INTERVIEW_REPORT_ASYNC,
    )
    logger.info("Max retry attempts per message: %d", settings.INTERVIEW_REPORT_MAX_ATTEMPTS)
    consume(
        topics=[settings.KAFKA_TOPIC_INTERVIEW_REPORT_ASYNC],
        handler=_handler_with_retry,
        group_id="ai-interview-report-transformers",
    )


if __name__ == "__main__":
    main()