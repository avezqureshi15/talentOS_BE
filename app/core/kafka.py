"""Kafka (Redpanda-compatible) plug-and-play client helpers.

Provides two global functions:

    from app.core.kafka import publish, consume

    publish(topic="my.topic", key="abc", value='{"msg": "hello"}')

    def handler(msg: ConsumedMessage) -> None:
        print(msg.value)

    consume(topics=["my.topic"], handler=handler, group_id="my-group")

Topic provisioning is handled by:

    ensure_topics([("my.topic", 6), ("my.topic.dlq", 1)])
"""
import signal
from dataclasses import dataclass
from typing import Callable

from confluent_kafka import Consumer, KafkaError, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_producer: Producer | None = None


# ── Public types ────────────────────────────────────────────────────────────


@dataclass
class ConsumedMessage:
    topic: str
    key: str | None
    value: str | None
    partition: int
    offset: int


# ── Producer ────────────────────────────────────────────────────────────────


def get_producer() -> Producer:
    """Return the lazily-initialised singleton Kafka producer."""
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
                "socket.connection.setup.timeout.ms": 5000,
                "log_level": 0,
            }
        )
        logger.info("Kafka producer initialised | servers=%s", settings.KAFKA_BOOTSTRAP_SERVERS)
    return _producer


def publish(topic: str, key: str, value: str) -> None:
    """Synchronously publish a single message and wait for broker ack."""
    producer = get_producer()
    delivery: dict[str, Exception | None] = {"error": None}

    def _on_delivery(err, _msg) -> None:
        if err is not None:
            delivery["error"] = err

    producer.produce(topic=topic, key=key, value=value, callback=_on_delivery)
    producer.flush(timeout=10)

    if delivery["error"] is not None:
        raise RuntimeError(f"Kafka delivery failed: {delivery['error']}")


# ── Consumer ────────────────────────────────────────────────────────────────


def consume(
    topics: list[str],
    handler: Callable[[ConsumedMessage], None],
    group_id: str | None = None,
    auto_offset_reset: str = "earliest",
    max_poll_interval_ms: int = 600000,
) -> None:
    """Run a blocking Kafka consumer loop.

    Handles signal-based graceful shutdown (SIGINT/SIGTERM), poll errors,
    and at-least-once offset commit semantics.

    Parameters
    ----------
    topics:
        List of topic names to subscribe to.
    handler:
        Called for each consumed message after deserialising into
        ``ConsumedMessage``.  Must raise on failure so the offset is
        not committed (the message will be re-delivered).
    group_id:
        Consumer group for partition distribution.  Falls back to the
        module name of the caller if not provided.
    auto_offset_reset:
        Where to start when no committed offset exists.
    max_poll_interval_ms:
        Maximum time between polls before the broker considers the
        consumer dead.  Increase for handlers that may take minutes
        (e.g. AI inference).
    """
    if group_id is None:
        group_id = f"talentos-{topics[0].replace('.', '-')}" if topics else "talentos-unknown"

    running = True

    def _shutdown(signum, _frame) -> None:
        nonlocal running
        logger.info("Received signal %s — shutting down consumer gracefully", signum)
        running = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    consumer = Consumer(
        {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": group_id,
            "auto.offset.reset": auto_offset_reset,
            "enable.auto.commit": False,
            "max.poll.interval.ms": max_poll_interval_ms,
        }
    )
    consumer.subscribe(topics)

    logger.info(
        "Kafka consumer started | group=%s | topics=%s | servers=%s",
        group_id, topics, settings.KAFKA_BOOTSTRAP_SERVERS,
    )

    try:
        while running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("Consumer error: %s", msg.error())
                continue

            try:
                handler(
                    ConsumedMessage(
                        topic=msg.topic(),
                        key=msg.key().decode("utf-8") if msg.key() else None,
                        value=msg.value().decode("utf-8") if msg.value() else None,
                        partition=msg.partition(),
                        offset=msg.offset(),
                    )
                )
                consumer.commit(msg)
            except Exception as exc:
                logger.error("Handler failed — offset NOT committed (message will re-deliver): %s", exc)
    finally:
        consumer.close()
        logger.info("Kafka consumer stopped | group=%s", group_id)


# ── Topic provisioning ──────────────────────────────────────────────────────


def ensure_topics(topics: list[tuple[str, int]]) -> None:
    """Best-effort creation of Kafka topics.

    Safe to call on startup; ignores 'already exists' errors and never
    raises (Kafka may be unavailable in development).

    Parameters
    ----------
    topics:
        Each entry is a ``(topic_name, num_partitions)`` pair.
    """
    try:
        admin = AdminClient(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "socket.connection.setup.timeout.ms": 3000,
                "log_level": 0,
            }
        )
        new_topics = [
            NewTopic(name, num_partitions=parts, replication_factor=1)
            for name, parts in topics
        ]
        futures = admin.create_topics(new_topics)
        for name, future in futures.items():
            try:
                future.result(timeout=8)
                logger.info("Kafka topic ensured: %s", name)
            except Exception as exc:
                logger.info("Kafka topic '%s' not created (exists or broker down): %s", name, str(exc))
    except Exception as exc:
        logger.warning("Could not ensure Kafka topics (broker unreachable?): %s", str(exc))
