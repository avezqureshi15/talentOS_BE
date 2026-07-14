from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import get_logger
from app.modules.forms.form_model import Form, FormStatus, FormType
from app.modules.users.user_model import User

logger = get_logger(__name__)


class FormRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, form_id: UUID) -> Form | None:
        return self.db.query(Form).filter(Form.id == form_id).first()

    def get_latest(self, emp_id: str, form_type: str = FormType.SLOTS.value) -> Form | None:
        return (
            self.db.query(Form)
            .join(User, User.id == Form.employee_id)
            .filter(User.emp_id == emp_id, Form.type == form_type)
            .order_by(Form.last_sent_at.desc())
            .first()
        )

    def get_active_sent(self, emp_id: str, form_type: str = FormType.SLOTS.value) -> Form | None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.FORM_EXPIRY_HOURS)
        return (
            self.db.query(Form)
            .join(User, User.id == Form.employee_id)
            .filter(
                User.emp_id == emp_id,
                Form.type == form_type,
                Form.status == FormStatus.SENT.value,
                Form.last_sent_at > cutoff,
            )
            .order_by(Form.last_sent_at.desc())
            .first()
        )

    def get_latest_by_user(self, user_id: int, form_type: str = FormType.SLOTS.value) -> Form | None:
        return (
            self.db.query(Form)
            .filter(Form.employee_id == user_id, Form.type == form_type)
            .order_by(Form.last_sent_at.desc())
            .first()
        )

    def get_active_sent_by_user(self, user_id: int, form_type: str = FormType.SLOTS.value) -> Form | None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.FORM_EXPIRY_HOURS)
        return (
            self.db.query(Form)
            .filter(
                Form.employee_id == user_id,
                Form.type == form_type,
                Form.status == FormStatus.SENT.value,
                Form.last_sent_at > cutoff,
            )
            .order_by(Form.last_sent_at.desc())
            .first()
        )

    def get_active_sent_by_user_and_round(self, user_id: int, round_id: UUID) -> Form | None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.FORM_EXPIRY_HOURS)
        return (
            self.db.query(Form)
            .filter(
                Form.employee_id == user_id,
                Form.type == FormType.REVIEW.value,
                Form.round_id == round_id,
                Form.status == FormStatus.SENT.value,
                Form.last_sent_at > cutoff,
            )
            .order_by(Form.last_sent_at.desc())
            .first()
        )

    def get_active_sent_by_emp_and_round(self, emp_id: str, round_id: UUID) -> Form | None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.FORM_EXPIRY_HOURS)
        return (
            self.db.query(Form)
            .join(User, User.id == Form.employee_id)
            .filter(
                User.emp_id == emp_id,
                Form.type == FormType.REVIEW.value,
                Form.round_id == round_id,
                Form.status == FormStatus.SENT.value,
                Form.last_sent_at > cutoff,
            )
            .order_by(Form.last_sent_at.desc())
            .first()
        )

    def create(self, employee_id: int, form_type: str, last_sent_at: datetime, round_id: UUID | None = None, candidate_id: int | None = None) -> Form:
        form = Form(
            employee_id=employee_id,
            type=form_type,
            status=FormStatus.SENT.value,
            last_sent_at=last_sent_at,
            round_id=round_id,
            candidate_id=candidate_id,
        )
        self.db.add(form)
        self.db.flush()
        logger.info("Created form: id=%s | employee_id=%s | type=%s", form.id, employee_id, form_type)
        return form

    def touch_last_sent_at(self, form: Form, last_sent_at: datetime) -> Form:
        form.last_sent_at = last_sent_at
        self.db.flush()
        logger.debug("Touched form last_sent_at: id=%s", form.id)
        return form

    def mark_submitted(self, form: Form) -> Form:
        form.status = FormStatus.SUBMITTED.value
        self.db.flush()
        logger.info("Marked form submitted: id=%s | emp_id=%s", form.id, form.employee.emp_id)
        return form

    def mark_expired(self, form: Form) -> Form:
        form.status = FormStatus.EXPIRED.value
        self.db.flush()
        logger.info("Marked form expired: id=%s | emp_id=%s", form.id, form.employee.emp_id)
        return form

    def _list_by_type_and_status(
        self, form_type: str, status: str,
        sent_before: str | None = None,
        sent_after: str | None = None,
    ) -> list[Form]:
        query = self.db.query(Form).filter(
            Form.type == form_type,
            Form.status == status,
        )
        if sent_before:
            query = query.filter(Form.last_sent_at <= func.now() - text(sent_before))
        if sent_after:
            query = query.filter(Form.last_sent_at > func.now() - text(sent_after))
        return query.all()

    def list_due_for_reminder(self) -> list[Form]:
        _reminder = f"INTERVAL '{settings.FORM_REMINDER_HOURS} hours'"
        _escalation = f"INTERVAL '{settings.FORM_ESCALATION_HOURS} hours'"
        rows = self._list_by_type_and_status(
            FormType.SLOTS.value, FormStatus.SENT.value,
            sent_before=_reminder,
            sent_after=_escalation,
        ) + self._list_by_type_and_status(
            FormType.REVIEW.value, FormStatus.SENT.value,
            sent_before=_reminder,
            sent_after=_escalation,
        )
        return [f for f in rows if f.reminded_at is None]

    def list_due_for_escalation(self) -> list[Form]:
        _escalation = f"INTERVAL '{settings.FORM_ESCALATION_HOURS} hours'"
        rows = self._list_by_type_and_status(
            FormType.SLOTS.value, FormStatus.SENT.value,
            sent_before=_escalation,
        ) + self._list_by_type_and_status(
            FormType.REVIEW.value, FormStatus.SENT.value,
            sent_before=_escalation,
        )
        return rows

    def list_expired(self) -> list[Form]:
        _expiry = f"INTERVAL '{settings.FORM_EXPIRY_HOURS} hours'"
        rows = self._list_by_type_and_status(
            FormType.SLOTS.value, FormStatus.SENT.value,
            sent_before=_expiry,
        ) + self._list_by_type_and_status(
            FormType.REVIEW.value, FormStatus.SENT.value,
            sent_before=_expiry,
        )
        return rows
