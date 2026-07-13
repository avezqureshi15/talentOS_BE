import uuid

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.events.event_model import Event
from app.modules.events.event_repository import EventRepository, EventRepositoryProtocol
from app.modules.events.event_schema import EventCreate, EventResponse, EventUpdate

logger = get_logger(__name__)


class EventService:
    def __init__(self, db: Session, repo: EventRepositoryProtocol | None = None):
        self.db = db
        self.repository = repo or EventRepository(db)

    def create_event(self, data: EventCreate) -> EventResponse:
        logger.info("Creating event: entity_type=%s | entity_id=%s | event_name=%s", data.entity_type, data.entity_id, data.event_name)
        event = Event(
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            job_id=data.job_id,
            candidate_id=data.candidate_id,
            event_name=data.event_name,
            state_code=data.state_code,
            actor_type=data.actor_type,
            actor_id=data.actor_id,
            remark=data.remark,
            action_url=data.action_url,
            action_label=data.action_label,
            event_metadata=data.event_metadata,
        )
        self.repository.create(event)
        self.db.commit()
        self.db.refresh(event)
        return EventResponse.model_validate(event)

    def update_event(self, event_id: uuid.UUID, data: EventUpdate) -> EventResponse:
        logger.info("Updating event: id=%s", event_id)
        event = self.repository.get_by_id(event_id)
        if not event:
            from app.common.exceptions.event_exception import EventNotFoundException
            raise EventNotFoundException(event_id)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(event, key, value)
        self.repository.update(event)
        self.db.commit()
        self.db.refresh(event)
        return EventResponse.model_validate(event)

    def get_events_by_entity(self, entity_type: str, entity_id: str) -> list[EventResponse]:
        events = self.repository.get_by_entity(entity_type, entity_id)
        return [EventResponse.model_validate(e) for e in events]

    def get_events_by_job(self, job_id: uuid.UUID) -> list[EventResponse]:
        events = self.repository.get_by_job(job_id)
        return [EventResponse.model_validate(e) for e in events]

    def get_event_by_id(self, event_id: uuid.UUID) -> EventResponse:
        event = self.repository.get_by_id(event_id)
        if not event:
            from app.common.exceptions.event_exception import EventNotFoundException
            raise EventNotFoundException(event_id)
        return EventResponse.model_validate(event)
