import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.events.event_schema import EventCreate, EventResponse, EventUpdate
from app.modules.events.event_service import EventService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/events", tags=["events"])


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(data: EventCreate, db: Session = Depends(get_db)):
    service = EventService(db)
    return service.create_event(data)


@router.get("/{event_id}", response_model=EventResponse)
def get_event_by_id(event_id: uuid.UUID, db: Session = Depends(get_db)):
    service = EventService(db)
    return service.get_event_by_id(event_id)


@router.patch("/{event_id}", response_model=EventResponse)
def update_event(event_id: uuid.UUID, data: EventUpdate, db: Session = Depends(get_db)):
    service = EventService(db)
    return service.update_event(event_id, data)


@router.get("", response_model=list[EventResponse])
def list_events(
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    job_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    service = EventService(db)
    if entity_type and entity_id:
        return service.get_events_by_entity(entity_type, entity_id)
    if job_id:
        return service.get_events_by_job(job_id)
    return []
