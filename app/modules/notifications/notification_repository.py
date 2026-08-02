from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, or_, update
from sqlalchemy.orm import Session

from app.modules.notifications.notification_model import Notification
from app.modules.users.user_model import User


class NotificationRepositoryProtocol(Protocol):
    def get_by_id(self, notification_id) -> Notification | None: ...
    def get_by_dedupe_key(self, employee_id: int, dedupe_key: str) -> Notification | None: ...
    def list_for_user(self, employee_id: int, page: int, per_page: int, notification_type: str | None = None, is_read: bool | None = None, types: list[str] | None = None, exclude_types: list[str] | None = None, search: str | None = None) -> tuple[list[Notification], int]: ...
    def create(self, employee_id: int, notification_type: str, title: str, body: str | None, action_url: str | None, action_label: str | None, form_id: UUID | None, job_id: UUID | None, candidate_id: int | None, dedupe_key: str | None) -> Notification: ...
    def mark_read(self, notification: Notification) -> Notification: ...
    def mark_all_read(self, employee_id: int, notification_type: str | None = None) -> int: ...
    def get_unread_count(self, employee_id: int) -> int: ...
    def decrement_unread(self, employee_id: int, amount: int = 1) -> None: ...


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, notification_id) -> Notification | None:
        return self.db.query(Notification).filter(Notification.id == notification_id).first()

    def get_by_dedupe_key(self, employee_id: int, dedupe_key: str) -> Notification | None:
        return (
            self.db.query(Notification)
            .filter(Notification.employee_id == employee_id, Notification.dedupe_key == dedupe_key)
            .first()
        )

    def list_for_user(
        self,
        employee_id: int,
        page: int,
        per_page: int,
        notification_type: str | None = None,
        is_read: bool | None = None,
        types: list[str] | None = None,
        exclude_types: list[str] | None = None,
        search: str | None = None,
    ) -> tuple[list[Notification], int]:
        query = self.db.query(Notification).filter(Notification.employee_id == employee_id)
        if notification_type:
            query = query.filter(Notification.type == notification_type)
        if types:
            query = query.filter(Notification.type.in_(types))
        if exclude_types:
            query = query.filter(~Notification.type.in_(exclude_types))
        if is_read is not None:
            query = query.filter(Notification.is_read == is_read)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(or_(Notification.title.ilike(pattern), Notification.body.ilike(pattern)))
        total = query.count()
        items = (
            query.order_by(Notification.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total

    def create(
        self,
        employee_id: int,
        notification_type: str,
        title: str,
        body: str | None,
        action_url: str | None,
        action_label: str | None,
        form_id: UUID | None,
        job_id: UUID | None,
        candidate_id: int | None,
        dedupe_key: str | None,
    ) -> Notification:
        notification = Notification(
            employee_id=employee_id,
            type=notification_type,
            title=title,
            body=body,
            action_url=action_url,
            action_label=action_label,
            form_id=form_id,
            job_id=job_id,
            candidate_id=candidate_id,
            dedupe_key=dedupe_key,
            is_read=False,
        )
        self.db.add(notification)
        self.db.flush()
        self.db.execute(
            update(User)
            .where(User.id == employee_id)
            .values(unread_count=User.unread_count + 1)
        )
        return notification

    def mark_read(self, notification: Notification) -> Notification:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        self.db.flush()
        return notification

    def mark_all_read(self, employee_id: int, notification_type: str | None = None) -> int:
        query = self.db.query(Notification).filter(
            Notification.employee_id == employee_id,
            Notification.is_read.is_(False),
        )
        if notification_type:
            query = query.filter(Notification.type == notification_type)
        unread_ids = [row.id for row in query.with_entities(Notification.id).all()]
        if not unread_ids:
            return 0
        self.db.query(Notification).filter(Notification.id.in_(unread_ids)).update(
            {
                Notification.is_read: True,
                Notification.read_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
        self.decrement_unread(employee_id, amount=len(unread_ids))
        return len(unread_ids)

    def get_unread_count(self, employee_id: int) -> int:
        user = self.db.query(User.unread_count).filter(User.id == employee_id).first()
        return user[0] if user and user[0] is not None else 0

    def decrement_unread(self, employee_id: int, amount: int = 1) -> None:
        self.db.execute(
            update(User)
            .where(User.id == employee_id, User.unread_count > 0)
            .values(unread_count=User.unread_count - amount)
        )
