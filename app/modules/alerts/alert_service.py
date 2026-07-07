from uuid import UUID

from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.common.exceptions.alert_exception import AlertNotFoundException
from app.modules.alerts.alert_model import Alert, AlertType
from app.modules.alerts.alert_repository import AlertRepository
from app.modules.alerts.alert_schema import AlertResponse, PaginatedAlertResponse
from app.modules.forms.form_mail import build_slot_link
from app.modules.forms.form_repository import FormRepository
from app.modules.users.user_repository import UserRepository


class AlertService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AlertRepository(db)
        self.user_repository = UserRepository(db)
        self.form_repository = FormRepository(db)

    def _enrich_alert(self, alert: Alert) -> AlertResponse:
        user = self.user_repository.get_by_emp_id(alert.emp_id)
        form = None
        if alert.type == AlertType.SLOTS.value:
            form = self.form_repository.get_active_sent(alert.emp_id)

        return AlertResponse(
            id=alert.id,
            emp_id=alert.emp_id,
            type=alert.type,
            is_read=alert.is_read,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
            name=user.name if user and user.name else alert.emp_id,
            email=user.email if user and user.email else "",
            phone_number=user.phone_number if user and user.phone_number else "",
            form_link=build_slot_link(form.id) if form else None,
        )

    def list_alerts(
        self,
        page: int,
        per_page: int,
        emp_id: str | None = None,
        alert_type: str | None = None,
        is_read: bool | None = None,
    ) -> PaginatedAlertResponse:
        alerts, total = self.repository.list_paginated(
            page=page,
            per_page=per_page,
            emp_id=emp_id,
            alert_type=alert_type,
            is_read=is_read,
        )
        return PaginatedAlertResponse(
            data=[self._enrich_alert(alert) for alert in alerts],
            total=total,
            page=page,
            per_page=per_page,
            has_more=(page * per_page) < total,
        )

    def mark_alert_read(self, alert_id: UUID) -> AlertResponse:
        alert = self.repository.get_by_id(alert_id)
        if not alert:
            raise AlertNotFoundException(str(alert_id))

        if alert.is_read:
            return AlertResponse.model_validate(alert)

        try:
            updated = self.repository.mark_read(alert)
            self.db.commit()
            self.db.refresh(updated)
        except sa_exc.SQLAlchemyError:
            self.db.rollback()
            raise
        return AlertResponse.model_validate(updated)

    def create_alert_if_missing(self, emp_id: str, alert_type: str = AlertType.SLOTS.value) -> None:
        if self.repository.get_unread_by_emp_and_type(emp_id, alert_type):
            return
        try:
            self.repository.create(emp_id=emp_id, alert_type=alert_type)
            self.db.commit()
        except sa_exc.SQLAlchemyError:
            self.db.rollback()
            raise

    def mark_emp_alerts_read(self, emp_id: str, alert_type: str = AlertType.SLOTS.value) -> None:
        try:
            self.repository.mark_all_read(emp_id, alert_type)
            self.db.commit()
        except sa_exc.SQLAlchemyError:
            self.db.rollback()
            raise
