from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import AllowedUser
from app.models.notification import Notification
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=List[NotificationOut])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.recipient_email == current_user.email)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    await db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.recipient_email == current_user.email,
        )
        .values(is_read=True)
    )
    return {"message": "Marked as read"}


@router.put("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    await db.execute(
        update(Notification)
        .where(Notification.recipient_email == current_user.email)
        .values(is_read=True)
    )
    return {"message": "All notifications marked as read"}
