from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.models.audit import AuditEvent


class AuditService:
    @staticmethod
    async def log(
        db: AsyncSession,
        entity_type: str,
        entity_id: UUID,
        event_type: str,
        actor_email: str,
        payload: dict = None,
    ) -> AuditEvent:
        event = AuditEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            actor_email=actor_email,
            payload=payload or {},
        )
        db.add(event)
        await db.flush()
        return event
