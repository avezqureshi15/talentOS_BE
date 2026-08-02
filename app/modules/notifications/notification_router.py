from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.auth.auth_dependencies import get_current_user
from app.modules.auth.auth_schema import UserInfo
from app.modules.notifications.notification_model import NotificationType
from app.modules.notifications.notification_schema import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
    UnreadCountData,
)
from app.modules.notifications.notification_service import NotificationService

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/notifications",
    tags=["notifications"],
)


@router.get("/", response_model=NotificationListResponse)
def list_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    type: NotificationType | None = Query(default=None, description="Notification type (e.g. SLOTS, REVIEW)"),
    types: str | None = Query(default=None, description="Comma-separated notification types (e.g. REVIEW,REVIEW_SUBMITTED)"),
    exclude_types: str | None = Query(default=None, description="Comma-separated notification types to exclude (e.g. SLOTS,REVIEW)"),
    is_read: bool | None = Query(default=None),
    search: str | None = Query(default=None, description="Search title/body"),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    return NotificationService(db).list_mine(
        employee_id=current_user.id,
        page=page,
        per_page=per_page,
        notification_type=type.value if type else None,
        types=[t.strip() for t in types.split(",") if t.strip()] if types else None,
        exclude_types=[t.strip() for t in exclude_types.split(",") if t.strip()] if exclude_types else None,
        is_read=is_read,
        search=search,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    count = NotificationService(db).get_unread_count(employee_id=current_user.id)
    return UnreadCountResponse(data=UnreadCountData(unread_count=count))


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    return NotificationService(db).mark_read(notification_id, employee_id=current_user.id)


@router.patch("/read-all", response_model=dict)
def mark_all_read(
    type: NotificationType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    updated = NotificationService(db).mark_all_read(employee_id=current_user.id, notification_type=type.value if type else None)
    return {"success": True, "data": {"updated": updated}}
