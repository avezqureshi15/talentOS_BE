import uuid
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.events.event_model import Event

logger = get_logger(__name__)


class EventRepositoryProtocol(Protocol):
    def create(self, event: Event) -> Event: ...
    def get_by_id(self, event_id: uuid.UUID) -> Event | None: ...
    def update(self, event: Event) -> Event: ...
    def get_by_entity(self, entity_type: str, entity_id: str) -> list[Event]: ...
    def get_by_job(self, job_id: uuid.UUID) -> list[Event]: ...
    def get_by_candidate_id(self, candidate_id: int) -> list[Event]: ...


class EventRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, event: Event) -> Event:
        logger.info("Persisting event: entity_type=%s | entity_id=%s | event_name=%s", event.entity_type, event.entity_id, event.event_name)
        self.db.add(event)
        self.db.flush()
        return event

    def get_by_id(self, event_id: uuid.UUID) -> Event | None:
        return self.db.query(Event).filter(Event.id == event_id).first()

    def update(self, event: Event) -> Event:
        logger.info("Updating event: id=%s", event.id)
        self.db.flush()
        return event

    def get_by_entity(self, entity_type: str, entity_id: str) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.entity_type == entity_type, Event.entity_id == entity_id)
            .order_by(Event.created_at.desc())
            .all()
        )

    def get_by_job(self, job_id: uuid.UUID) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.job_id == job_id)
            .order_by(Event.created_at.desc())
            .all()
        )

    def get_by_candidate_id(self, candidate_id: int) -> list[Event]:
        logger.debug("Fetching events: candidate_id=%d", candidate_id)
        return (
            self.db.query(Event)
            .filter(Event.candidate_id == candidate_id)
            .order_by(Event.created_at.asc())
            .all()
        )
