from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.common.utils.list_utils import unique_preserve_order
from app.core.logger import get_logger
from app.modules.alerts.alert_model import AlertType
from app.modules.forms.form_mail import (
    DETAIL_NEW_LINK,
    DETAIL_RESENT,
    MSG_EMP_NOT_FOUND,
    MSG_INVALID_EMAIL,
    MSG_SMTP_NOT_CONFIGURED,
    build_ask_summary_message,
    detail_to_message,
    is_form_expired,
    is_smtp_configured,
    is_valid_email,
    send_slot_mail_task,
)
from app.modules.forms.form_model import Form, FormStatus, FormType
from app.modules.forms.form_repository import FormRepository
from app.modules.forms.form_schema import (
    AskFormResponse,
    AskFormResultItem,
    FormValidateResponse,
    PendingMailTask,
)
from app.modules.users.user_repository import UserRepository

logger = get_logger(__name__)


class FormService:
    def __init__(self, db: Session):
        from app.modules.alerts.alert_service import AlertService
        self.db = db
        self.repository = FormRepository(db)
        self.user_repository = UserRepository(db)
        self.alert_service = AlertService(db)

    def _resolve_ask_action(self, emp_id: str, form_type: str) -> tuple[Form, str]:
        now = datetime.now(timezone.utc)
        active = self.repository.get_active_sent(emp_id, form_type)
        if active:
            self.repository.touch_last_sent_at(active, last_sent_at=now)
            return active, DETAIL_RESENT

        latest = self.repository.get_latest(emp_id, form_type)
        if latest and latest.status == FormStatus.SENT.value and is_form_expired(latest):
            self.repository.mark_expired(latest)

        form = self.repository.create(emp_id=emp_id, form_type=form_type, last_sent_at=now)
        return form, DETAIL_NEW_LINK

    def ask_form_batch(self, emp_ids: list[str], form_type: str) -> tuple[AskFormResponse, list[PendingMailTask]]:
        results: list[AskFormResultItem] = []
        mail_tasks: list[PendingMailTask] = []
        smtp_ready = is_smtp_configured()

        for emp_id in unique_preserve_order(emp_ids):
            if not smtp_ready:
                results.append(
                    AskFormResultItem(
                        emp_id=emp_id,
                        status="FAILED",
                        message=MSG_SMTP_NOT_CONFIGURED,
                    )
                )
                continue

            user = self.user_repository.get_by_emp_id(emp_id)
            if not user:
                results.append(
                    AskFormResultItem(
                        emp_id=emp_id,
                        status="FAILED",
                        message=MSG_EMP_NOT_FOUND,
                    )
                )
                continue

            if not is_valid_email(user.email):
                results.append(
                    AskFormResultItem(
                        emp_id=emp_id,
                        status="FAILED",
                        message=MSG_INVALID_EMAIL,
                    )
                )
                continue

            try:
                form, detail = self._resolve_ask_action(emp_id, form_type)
                self.db.flush()
                results.append(
                    AskFormResultItem(
                        emp_id=emp_id,
                        status="SUCCESS",
                        message=detail_to_message(detail),
                    )
                )
                mail_tasks.append(PendingMailTask(emp_id=emp_id, form_id=form.id))
            except sa_exc.SQLAlchemyError:
                self.db.rollback()
                raise

        try:
            self.db.commit()
        except sa_exc.SQLAlchemyError:
            self.db.rollback()
            raise

        success_ids = [r.emp_id for r in results if r.status == "SUCCESS"]
        return (
            AskFormResponse(
                message=build_ask_summary_message(success_ids),
                results=results,
            ),
            mail_tasks,
        )

    def validate_form(self, form_id: UUID) -> FormValidateResponse:
        form = self.repository.get_by_id(form_id)
        if not form:
            return FormValidateResponse(valid=False, reason="NOT_FOUND")
        if form.status == FormStatus.SUBMITTED.value:
            return FormValidateResponse(
                valid=False, reason="ALREADY_SUBMITTED", emp_id=form.emp_id, type=form.type
            )
        if form.status == FormStatus.EXPIRED.value:
            return FormValidateResponse(valid=False, reason="EXPIRED", emp_id=form.emp_id, type=form.type)
        if is_form_expired(form):
            if form.status == FormStatus.SENT.value:
                try:
                    self.repository.mark_expired(form)
                    self.db.commit()
                    self.alert_service.mark_emp_alerts_read(
                        form.emp_id, alert_type=form.type
                    )
                except sa_exc.SQLAlchemyError:
                    self.db.rollback()
                    raise
            return FormValidateResponse(valid=False, reason="EXPIRED", emp_id=form.emp_id, type=form.type)
        return FormValidateResponse(valid=True, reason="VALID", emp_id=form.emp_id, type=form.type)

    def mark_slots_form_submitted(self, emp_id: str) -> None:
        form = self.repository.get_active_sent(emp_id, FormType.SLOTS.value)
        if not form:
            form = self.repository.get_latest(emp_id, FormType.SLOTS.value)
        if not form or form.status != FormStatus.SENT.value:
            return
        try:
            self.repository.mark_submitted(form)
            self.db.commit()
        except sa_exc.SQLAlchemyError:
            self.db.rollback()
            raise
        self.alert_service.mark_emp_alerts_read(emp_id=emp_id, alert_type=AlertType.SLOTS.value)

    def run_reminder_job(self) -> int:
        forms = self.repository.list_due_for_reminder()
        sent = 0
        for form in forms:
            send_slot_mail_task(form.emp_id, form.id)
            sent += 1
        return sent

    def run_escalation_job(self) -> int:
        forms = self.repository.list_due_for_escalation()
        created = 0
        for form in forms:
            if self.alert_service.repository.get_unread_by_emp_and_type(
                form.emp_id, AlertType.SLOTS.value
            ):
                continue
            self.alert_service.create_alert_if_missing(form.emp_id, AlertType.SLOTS.value)
            created += 1
        return created

    def run_expiry_reconciliation_job(self) -> int:
        forms = self.repository.list_expired()
        updated = 0
        for form in forms:
            try:
                self.repository.mark_expired(form)
                self.alert_service.mark_emp_alerts_read(
                    form.emp_id, alert_type=AlertType.SLOTS.value
                )
                updated += 1
            except sa_exc.SQLAlchemyError:
                self.db.rollback()
                raise
        if updated:
            self.db.commit()
        return updated
