"""Kafka (Redpanda-compatible) client helpers.

Provides a process-wide singleton Producer for the API/ingest layer and a
best-effort topic provisioner. Consumers build their own Consumer instances
(see app/workers/evaluation_worker.py) because each worker process owns its
own consumer in the `resume-evaluators` group.
"""
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_producer: Producer | None = None


def get_producer() -> Producer:
    """Return the lazily-initialised singleton Kafka producer.

    Configured for durability (acks=all) and exactly-once-ish producer
    semantics (idempotence) so retries never write duplicate messages.
    """
    global _producer
    if _producer is None:
        _producer = Producer(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "acks": "all",
                "enable.idempotence": True,
                "retries": 5,
                "linger.ms": 50,
                "client.id": "talentos-be-producer",
                # Fail fast and stay quiet when the broker is unreachable instead
                # of flooding stderr with rdkafka FAIL lines.
                "socket.connection.setup.timeout.ms": 5000,
                "log_level": 0,
            }
        )
        logger.info("Kafka producer initialised | servers=%s", settings.KAFKA_BOOTSTRAP_SERVERS)
    return _producer


def publish(topic: str, key: str, value: str) -> None:
    """Synchronously publish a single message and wait for broker ack.

    Raises if the message could not be delivered so the caller can react
    (e.g. surface a 502 from the ingest endpoint).
    """
    producer = get_producer()
    delivery: dict[str, Exception | None] = {"error": None}

    def _on_delivery(err, _msg) -> None:
        if err is not None:
            delivery["error"] = err

    producer.produce(topic=topic, key=key, value=value, callback=_on_delivery)
    producer.flush(timeout=10)

    if delivery["error"] is not None:
        raise RuntimeError(f"Kafka delivery failed: {delivery['error']}")


def ensure_topics() -> None:
    """Best-effort topic creation. Safe to call on startup; ignores
    'already exists' and never raises (Kafka may be down in dev)."""
    try:
        admin = AdminClient(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                # Give up quickly and silently if the broker isn't up (dev),
                # rather than blocking startup ~60s and spamming the console.
                "socket.connection.setup.timeout.ms": 3000,
                "log_level": 0,
            }
        )
        topics = [
            NewTopic(
                settings.KAFKA_TOPIC_EVALUATION,
                num_partitions=settings.KAFKA_EVALUATION_PARTITIONS,
                replication_factor=1,
            ),
            NewTopic(
                settings.KAFKA_TOPIC_EVALUATION_DLQ,
                num_partitions=1,
                replication_factor=1,
            ),
        ]
        futures = admin.create_topics(topics)
        for name, future in futures.items():
            try:
                future.result(timeout=8)
                logger.info("Kafka topic ensured: %s", name)
            except Exception as exc:  # noqa: BLE001 — topic may already exist / broker down
                logger.info("Kafka topic '%s' not created (exists or broker down): %s", name, str(exc))
    except Exception as exc:  # noqa: BLE001 — never block startup on Kafka
        logger.warning("Could not ensure Kafka topics (broker unreachable?): %s", str(exc))
