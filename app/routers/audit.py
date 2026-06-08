from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import AllowedUser
from app.models.audit import AuditEvent

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/jobs/{job_id}")
async def get_job_audit(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    result = await db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.entity_type == "job_posting",
            AuditEvent.entity_id == job_id,
        )
        .order_by(AuditEvent.created_at.asc())
    )
    events = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "actor_email": e.actor_email,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/candidates/{candidate_id}")
async def get_candidate_audit(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    result = await db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.entity_type == "candidate",
            AuditEvent.entity_id == candidate_id,
        )
        .order_by(AuditEvent.created_at.asc())
    )
    events = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "actor_email": e.actor_email,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
