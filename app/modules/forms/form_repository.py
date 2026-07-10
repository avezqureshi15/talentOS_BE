from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.forms.form_model import Form, FormStatus, FormType

logger = get_logger(__name__)

FORM_VALIDITY_HOURS = 24


class FormRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, form_id: UUID) -> Form | None:
        return self.db.query(Form).filter(Form.id == form_id).first()

    def get_latest(self, emp_id: str, form_type: str = FormType.SLOTS.value) -> Form | None:
        return (
            self.db.query(Form)
            .filter(Form.emp_id == emp_id, Form.type == form_type)
            .order_by(Form.last_sent_at.desc())
            .first()
        )

    def get_active_sent(self, emp_id: str, form_type: str = FormType.SLOTS.value) -> Form | None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=FORM_VALIDITY_HOURS)
        return (
            self.db.query(Form)
            .filter(
                Form.emp_id == emp_id,
                Form.type == form_type,
                Form.status == FormStatus.SENT.value,
                Form.last_sent_at > cutoff,
            )
            .order_by(Form.last_sent_at.desc())
            .first()
        )

    def create(self, emp_id: str, form_type: str, last_sent_at: datetime) -> Form:
        form = Form(
            emp_id=emp_id,
            type=form_type,
            status=FormStatus.SENT.value,
            last_sent_at=last_sent_at,
        )
        self.db.add(form)
        self.db.flush()
        logger.info("Created form: id=%s | emp_id=%s | type=%s", form.id, emp_id, form_type)
        return form

    def touch_last_sent_at(self, form: Form, last_sent_at: datetime) -> Form:
        form.last_sent_at = last_sent_at
        self.db.flush()
        logger.debug("Touched form last_sent_at: id=%s", form.id)
        return form

    def mark_submitted(self, form: Form) -> Form:
        form.status = FormStatus.SUBMITTED.value
        self.db.flush()
        logger.info("Marked form submitted: id=%s | emp_id=%s", form.id, form.emp_id)
        return form

    def mark_expired(self, form: Form) -> Form:
        form.status = FormStatus.EXPIRED.value
        self.db.flush()
        logger.info("Marked form expired: id=%s | emp_id=%s", form.id, form.emp_id)
        return form

    def list_due_for_reminder(self) -> list[Form]:
        rows = (
            self.db.query(Form)
            .filter(
                Form.type == FormType.SLOTS.value,
                Form.status == FormStatus.SENT.value,
                Form.last_sent_at <= func.now() - text("INTERVAL '2 hours'"),
                Form.last_sent_at > func.now() - text("INTERVAL '3 hours'"),
            )
            .all()
        )
        logger.debug("Forms due for reminder: count=%s", len(rows))
        return rows

    def list_due_for_escalation(self) -> list[Form]:
        rows = (
            self.db.query(Form)
            .filter(
                Form.type == FormType.SLOTS.value,
                Form.status == FormStatus.SENT.value,
                Form.last_sent_at <= func.now() - text("INTERVAL '3 hours'"),
            )
            .all()
        )
        logger.debug("Forms due for escalation: count=%s", len(rows))
        return rows

    def list_expired(self) -> list[Form]:
        rows = (
            self.db.query(Form)
            .filter(
                Form.type == FormType.SLOTS.value,
                Form.status == FormStatus.SENT.value,
                Form.last_sent_at <= func.now() - text("INTERVAL '24 hours'"),
            )
            .all()
        )
        logger.debug("Forms expired: count=%s", len(rows))
        return rows
