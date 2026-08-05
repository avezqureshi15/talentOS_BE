from uuid import UUID

from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.common.exceptions.notification_exception import NotificationNotFoundException
from app.modules.notifications.notification_model import Notification, NotificationType
from app.modules.notifications.notification_repository import NotificationRepository, NotificationRepositoryProtocol
from app.modules.notifications.notification_schema import (
    NotificationListResponse,
    NotificationPagination,
    NotificationResponse,
    NotificationsData,
)


class NotificationService:
    def __init__(self, db: Session | None = None, repo: NotificationRepositoryProtocol | None = None):
        self.db = db
        self.repository = repo or (NotificationRepository(db) if db else None)

    @staticmethod
    def validate_type(notification_type: str) -> str:
        """Strictly validate a notification type against the registry.

        Adding a new notification type is a one-line change: add a member to
        ``NotificationType`` and call ``notify(...)`` — no schema changes.
        """
        try:
            return NotificationType(notification_type.upper()).value
        except ValueError:
            raise ValueError(f"Unknown notification type: {notification_type}")

    def notify(
        self,
        *,
        employee_id: int,
        notification_type: str,
        title: str,
        body: str | None = None,
        action_url: str | None = None,
        action_label: str | None = None,
        form_id: UUID | None = None,
        job_id: UUID | None = None,
        candidate_id: int | None = None,
        dedupe_key: str | None = None,
    ) -> Notification | None:
        """Create one notification. Deduplication is opt-in via ``dedupe_key``
        (DB-enforced unique per employee). Does NOT commit — callers own the
        transaction so producers can emit notifications atomically with their
        own writes.
        """
        ntype = self.validate_type(notification_type)
        if not self.repository:
            return None
        if dedupe_key and self.repository.get_by_dedupe_key(employee_id, dedupe_key):
            return None
        return self.repository.create(
            employee_id=employee_id,
            notification_type=ntype,
            title=title,
            body=body,
            action_url=action_url,
            action_label=action_label,
            form_id=form_id,
            job_id=job_id,
            candidate_id=candidate_id,
            dedupe_key=dedupe_key,
        )

    def notify_many(
        self,
        employee_ids: list[int],
        **kwargs,
    ) -> int:
        """Notify several employees with the same payload. Dedupe applies per
        employee. Returns the number of notifications actually created.
        """
        created = 0
        for employee_id in dict.fromkeys(employee_ids):
            if self.notify(employee_id=employee_id, **kwargs):
                created += 1
        return created

    def notify_job_team(
        self,
        hiring_request_id: UUID,
        **kwargs,
    ) -> int:
        """Fan out to every member of a job's team. ``job_id`` in the payload
        defaults to the hiring request id.
        """
        from app.modules.job_teams.job_team_model import JobTeamMember
        from app.modules.users.user_model import User

        if not self.db:
            return 0
        # Route via employees linkage; reverse to users.id since notifications
        # are user-scoped. Members without a linked user are silently skipped.
        member_ids = [
            row[0]
            for row in self.db.query(User.id)
            .join(JobTeamMember, JobTeamMember.employee_id == User.employee_id)
            .filter(
                JobTeamMember.hiring_request_id == hiring_request_id,
                User.employee_id.isnot(None),
            )
            .all()
        ]
        kwargs.setdefault("job_id", hiring_request_id)
        return self.notify_many(member_ids, **kwargs)

    def notify_tenant_users(
        self,
        tenant_id: int,
        roles: list[str] | None = None,
        **kwargs,
    ) -> int:
        """Fan out to every active user under a tenant, optionally restricted
        to a set of roles. Falls back to ``job_id``-style defaults passed in.
        """
        from app.modules.users.user_model import User

        if not self.db or tenant_id is None:
            return 0
        query = self.db.query(User.id).filter(
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
        )
        if roles:
            query = query.filter(User.role.in_(roles))
        user_ids = [row[0] for row in query.all()]
        return self.notify_many(user_ids, **kwargs)

    def notify_tenant_admins(
        self,
        tenant_id: int,
        **kwargs,
    ) -> int:
        """Fan out to the tenant's admins (account_admin / superadmin)."""
        return self.notify_tenant_users(
            tenant_id,
            roles=["account_admin", "superadmin"],
            **kwargs,
        )

    def list_mine(
        self,
        employee_id: int,
        page: int = 1,
        per_page: int = 20,
        notification_type: str | None = None,
        is_read: bool | None = None,
        types: list[str] | None = None,
        exclude_types: list[str] | None = None,
        search: str | None = None,
    ) -> NotificationListResponse:
        ntype = self.validate_type(notification_type) if notification_type else None
        if types:
            types = [self.validate_type(t) for t in types]
        if exclude_types:
            exclude_types = [self.validate_type(t) for t in exclude_types]
        if not self.repository:
            return self._empty(page, per_page)
        items, total = self.repository.list_for_user(
            employee_id=employee_id,
            page=page,
            per_page=per_page,
            notification_type=ntype,
            is_read=is_read,
            types=types,
            exclude_types=exclude_types,
            search=search,
        )
        return NotificationListResponse(data=NotificationsData(
            notifications=[NotificationResponse.model_validate(n) for n in items],
            pagination=NotificationPagination(
                current_page=page,
                per_page=per_page,
                total_records=total,
                has_more=(page * per_page) < total,
            ),
        ))

    def get_unread_count(self, employee_id: int) -> int:
        if not self.repository:
            return 0
        return self.repository.get_unread_count(employee_id)

    def mark_read(self, notification_id: UUID, employee_id: int) -> NotificationResponse:
        if not self.repository:
            raise NotificationNotFoundException(str(notification_id))
        notification = self.repository.get_by_id(notification_id)
        if not notification or notification.employee_id != employee_id:
            raise NotificationNotFoundException(str(notification_id))

        if not notification.is_read:
            try:
                self.repository.mark_read(notification)
                self.repository.decrement_unread(employee_id)
                self.db.commit()
            except sa_exc.SQLAlchemyError:
                self.db.rollback()
                raise
        return NotificationResponse.model_validate(notification)

    def mark_all_read(self, employee_id: int, notification_type: str | None = None) -> int:
        ntype = self.validate_type(notification_type) if notification_type else None
        if not self.repository:
            return 0
        try:
            updated = self.repository.mark_all_read(employee_id, notification_type=ntype)
            self.db.commit()
            return updated
        except sa_exc.SQLAlchemyError:
            self.db.rollback()
            raise

    @staticmethod
    def _empty(page: int, per_page: int) -> NotificationListResponse:
        return NotificationListResponse(data=NotificationsData(
            notifications=[],
            pagination=NotificationPagination(
                current_page=page,
                per_page=per_page,
                total_records=0,
                has_more=False,
            ),
        ))
