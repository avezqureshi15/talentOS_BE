from uuid import UUID

from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.common.exceptions.alert_exception import AlertNotFoundException
from app.modules.alerts.alert_model import Alert, AlertType
from app.modules.alerts.alert_repository import AlertRepository, AlertRepositoryProtocol
from app.modules.events.event_schema import EventCreate
from app.modules.events.event_service import EventService
from app.modules.alerts.alert_schema import (
    AlertListResponse,
    AlertListItem,
    AlertPagination,
    AlertResponse,
    AlertsData,
    EmployeeBrief,
    InterviewBrief,
    PaginatedAlertResponse,
)
from app.modules.forms.form_mail import build_slot_link
from app.modules.forms.form_repository import FormRepository
from app.modules.users.user_repository import UserRepository


class AlertService:
    def __init__(self, db: Session | None = None, repo: AlertRepositoryProtocol | None = None):
        self.db = db
        self.repository = repo or (AlertRepository(db) if db else None)
        self.user_repository = UserRepository(db) if db else None
        self.form_repository = FormRepository(db) if db else None

    def _enrich_alert(self, alert: Alert) -> AlertResponse:
        user = self.user_repository.get_by_id(alert.employee_id)
        form = None
        if alert.type == AlertType.SLOTS.value:
            if user:
                form = self.form_repository.get_active_sent(user.emp_id)

        return AlertResponse(
            id=alert.id,
            employee_id=alert.employee_id,
            form_id=alert.form_id,
            type=alert.type,
            is_read=alert.is_read,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
            name=user.name if user and user.name else str(alert.employee_id),
            email=user.email if user and user.email else "",
            phone_number=user.phone_number if user and user.phone_number else "",
            form_link=build_slot_link(form.id) if form else None,
        )

    @staticmethod
    def _map_alert_type(raw: str | None) -> str | None:
        if not raw:
            return None
        mapping = {"slots": "SLOTS", "reviews": "REVIEW"}
        return mapping.get(raw.lower())

    def list_alerts(
        self,
        page: int,
        per_page: int,
        employee_id: int | None = None,
        alert_type: str | None = None,
        is_read: bool | None = None,
    ) -> PaginatedAlertResponse:
        alerts, total = self.repository.list_paginated(
            page=page,
            per_page=per_page,
            employee_id=employee_id,
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

    def list_alerts_enriched(
        self,
        alert_type: str | None = None,
        page: int = 1,
        per_page: int = 20,
        is_read: bool | None = None,
    ) -> AlertListResponse:
        db_type = self._map_alert_type(alert_type)
        if not self.repository:
            return AlertListResponse(data=AlertsData(
                alerts=[], pagination=AlertPagination(
                    current_page=page, per_page=per_page, total_records=0, has_more=False,
                ),
            ))
        items, total = self.repository.list_enriched(
            page=page, per_page=per_page, alert_type=db_type, is_read=is_read,
        )
        alerts = [AlertListItem(**self._map_employee(item)) for item in items]
        pagination = AlertRepository.build_pagination(page, per_page, total)
        return AlertListResponse(data=AlertsData(
            alerts=alerts, pagination=AlertPagination(**pagination),
        ))

    def _map_employee(self, item: dict) -> dict:
        emp = item.pop("employee", {})
        item["employee"] = EmployeeBrief(**emp)
        if interview := item.get("interview"):
            item["interview"] = InterviewBrief(**interview)
        return item

    def mark_alert_read(self, alert_id: UUID) -> AlertResponse:
        alert = self.repository.get_by_id(alert_id)
        if not alert:
            raise AlertNotFoundException(str(alert_id))

        was_read = alert.is_read

        if alert.is_read:
            return AlertResponse.model_validate(alert)

        try:
            updated = self.repository.mark_read(alert)
            self.db.commit()
            self.db.refresh(updated)
        except sa_exc.SQLAlchemyError:
            self.db.rollback()
            raise

        if not was_read and alert.type == AlertType.REVIEW.value and alert.form_id:
            form = self.form_repository.get_by_id(alert.form_id) if self.form_repository else None
            if form and form.candidate_id:
                EventService(self.db).create_event(EventCreate(
                    entity_type="CANDIDATE",
                    entity_id=str(form.candidate_id),
                    candidate_id=form.candidate_id,
                    event_name="Review Alert Resolved",
                    state_code="REVIEW_ALERT_RESOLVED",
                    actor_type="HR",
                    event_metadata={
                        "form_id": str(form.id),
                        "alert_id": str(alert.id),
                    },
                ))

        return AlertResponse.model_validate(updated)

    def create_alert_if_missing(self, employee_id: int, alert_type: str = AlertType.SLOTS.value, form_id: UUID | None = None) -> bool:
        if form_id and self.repository.get_by_form_and_type(form_id, alert_type):
            return False
        try:
            self.repository.create(employee_id=employee_id, alert_type=alert_type, form_id=form_id)
            self.db.commit()
            return True
        except sa_exc.SQLAlchemyError:
            self.db.rollback()
            raise

    def mark_emp_alerts_read(self, employee_id: int, alert_type: str = AlertType.SLOTS.value) -> None:
        try:
            self.repository.mark_all_read(employee_id, alert_type)
            self.db.commit()
        except sa_exc.SQLAlchemyError:
            self.db.rollback()
            raise
