"""Resume evaluation Kafka consumer.

Run one process per worker; all processes share the consumer group
`resume-evaluators`, so Kafka distributes the topic's partitions across them.
For Phase 2 we run 3 replicas (see docker-compose `worker` service).

    python -m app.workers.evaluation_worker

Delivery semantics: at-least-once. The offset is committed only after the
message reaches a terminal outcome (stored result, INVALID, or routed to DLQ),
and processing is idempotent (terminal rows are skipped on re-delivery).
"""
import signal
import time

from confluent_kafka import Consumer, KafkaError

from app.core.config import settings
from app.core.kafka import publish
from app.core.logger import get_logger, setup_logging
from app.db.session import SessionLocal
from app.modules.evaluations.evaluation_processor import (
    EvaluationProcessor,
    TransientEvaluationError,
)
from app.modules.evaluations.evaluation_schema import EvaluationMessage

logger = get_logger(__name__)

_running = True


def _shutdown(signum, _frame) -> None:
    global _running
    logger.info("Received signal %s — shutting down worker gracefully", signum)
    _running = False


def _build_consumer() -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": settings.KAFKA_CONSUMER_GROUP,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "max.poll.interval.ms": 600000,  # 10 min — AI calls can be slow
        }
    )


def _handle_message(raw_value: bytes) -> None:
    """Process one message with bounded retry, then route to DLQ on failure."""
    message = EvaluationMessage.model_validate_json(raw_value)
    max_attempts = settings.EVALUATION_MAX_ATTEMPTS

    for attempt in range(1, max_attempts + 1):
        db = SessionLocal()
        try:
            EvaluationProcessor(db).process(message)
            return
        except TransientEvaluationError as exc:
            logger.warning(
                "Transient error (attempt %d/%d) for application_id=%s: %s",
                attempt,
                max_attempts,
                message.application_id,
                str(exc),
            )
            if attempt < max_attempts:
                time.sleep(min(2 ** attempt, 30))
            else:
                _route_to_dlq(message, str(exc))
        except Exception as exc:  # noqa: BLE001 — non-retryable; fail fast to DLQ
            logger.error(
                "Non-retryable error for application_id=%s: %s", message.application_id, str(exc)
            )
            _route_to_dlq(message, f"non-retryable: {exc}")
            return
        finally:
            db.close()


def _route_to_dlq(message: EvaluationMessage, reason: str) -> None:
    logger.error("Routing application_id=%s to DLQ: %s", message.application_id, reason)
    db = SessionLocal()
    try:
        from app.modules.evaluations.evaluation_model import EvaluationStatus
        from app.modules.evaluations.evaluation_repository import EvaluationRepository

        repo = EvaluationRepository(db)
        evaluation = repo.get_by_application_id(message.application_id)
        if evaluation is not None:
            repo.mark_result(evaluation, EvaluationStatus.FAILED, error_reason=reason[:1000])
    finally:
        db.close()

    try:
        publish(
            topic=settings.KAFKA_TOPIC_EVALUATION_DLQ,
            key=message.application_id,
            value=message.model_dump_json(),
        )
    except Exception as exc:  # noqa: BLE001 — DB already marked FAILED
        logger.error("Failed to publish to DLQ for application_id=%s: %s", message.application_id, str(exc))


def main() -> None:
    setup_logging()
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    consumer = _build_consumer()
    consumer.subscribe([settings.KAFKA_TOPIC_EVALUATION])
    logger.info(
        "Evaluation worker started | group=%s | topic=%s | servers=%s",
        settings.KAFKA_CONSUMER_GROUP,
        settings.KAFKA_TOPIC_EVALUATION,
        settings.KAFKA_BOOTSTRAP_SERVERS,
    )

    try:
        while _running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("Consumer error: %s", msg.error())
                continue

            try:
                _handle_message(msg.value())
            except Exception as exc:  # noqa: BLE001 — never crash the loop
                logger.error("Unhandled processing error: %s", str(exc))
            finally:
                # at-least-once: commit only after the message is fully handled
                consumer.commit(msg)
    finally:
        consumer.close()
        logger.info("Evaluation worker stopped")


if __name__ == "__main__":
    main()
