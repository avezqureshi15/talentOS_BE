import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.common.services.email_service import EmailService
from app.core.config import settings
from app.core.frontend import build_frontend_link
from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.email.email_template_service import render as render_email_template
from app.modules.employees.employee_model import Employee
from app.modules.forms.form_model import Form

logger = get_logger(__name__)

DETAIL_NEW_LINK = "NEW_LINK_SENT"
DETAIL_RESENT = "RESENT_EXISTING_LINK"

MSG_NEW_LINK = "New link sent"
MSG_RESENT = "Existing link resent"
MSG_EMP_NOT_FOUND = "Employee not found"
MSG_INVALID_EMAIL = "Invalid or missing email"
MSG_SMTP_NOT_CONFIGURED = "Email service not configured"
MSG_REVIEW_MAIL_SENT = "Review form mail sent"

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str | None) -> bool:
    if not email or not email.strip():
        return False
    return bool(_EMAIL_PATTERN.match(email.strip()))


def is_smtp_configured() -> bool:
    return bool(settings.SMTP_USERNAME.strip() and settings.SMTP_PASSWORD.strip())


def build_slot_link(form_id: UUID) -> str:
    return build_frontend_link(f"/book-slot/{form_id}")


def build_review_link(form_id: UUID) -> str:
    return build_frontend_link(f"/rate-candidate/{form_id}")


def detail_to_message(detail: str) -> str:
    if detail == DETAIL_RESENT:
        return MSG_RESENT
    return MSG_NEW_LINK


def build_ask_summary_message(success_labels: list[str]) -> str:
    """``success_labels`` is a display list (names preferred; caller falls back
    to emp_id when a name is missing)."""
    if not success_labels:
        return "No slot selection mails were queued."
    if len(success_labels) == 1:
        return f"Slot selection mails are being sent to {success_labels[0]}."
    joined = " and ".join(success_labels)
    return f"Slot selection mails are being sent to {joined}."


def send_slot_mail_task(
    employee_id: int,
    form_id: UUID,
    is_reminder: bool = False,
    requester_name: str | None = None,
) -> None:
    """Background mail task keyed by employees.id — the directory identity.
    Fetches the Employee row (not User) so HR-only employees also work."""
    if not is_smtp_configured():
        logger.warning("Background mail skipped for employee_id=%s: SMTP not configured", employee_id)
        return

    db = SessionLocal()
    try:
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            logger.warning("Background mail skipped: employee_id=%s not found", employee_id)
            return
        if not is_valid_email(employee.email):
            logger.warning(
                "Background mail skipped for employee_id=%s: invalid or missing email",
                employee_id,
            )
            return

        display_name = employee.name or str(employee_id)
        link = build_slot_link(form_id)
        email_service = EmailService(
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
        )
        subject, body, html = render_email_template(
            db,
            "slot_form_reminder" if is_reminder else "slot_form",
            {
                "recipient_name": display_name,
                "requester_name": requester_name,
                "form_url": link,
            },
        )
        email_service.send(to_email=employee.email.strip(), subject=subject, body=body, html=html)
    except Exception as exc:
        logger.warning("Background mail failed for employee_id=%s: %s", employee_id, exc)
    finally:
        db.close()


def send_review_mail_task(
    employee_id: int,
    form_id: UUID,
    candidate_name: str | None = None,
    round_name: str | None = None,
    interviewer_name: str | None = None,
    is_reminder: bool = False,
    requester_name: str | None = None,
    scheduled_at_label: str | None = None,
) -> None:
    if not is_smtp_configured():
        logger.warning("Background review mail skipped for employee_id=%s: SMTP not configured", employee_id)
        return

    db = SessionLocal()
    try:
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            logger.warning("Background review mail skipped: employee_id=%s not found", employee_id)
            return
        if not is_valid_email(employee.email):
            logger.warning(
                "Background review mail skipped for employee_id=%s: invalid or missing email",
                employee_id,
            )
            return

        display_name = interviewer_name or employee.name or str(employee_id)
        link = build_review_link(form_id)
        email_service = EmailService(
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
        )
        subject, body, html = render_email_template(
            db,
            "review_form_reminder" if is_reminder else "review_form",
            {
                "recipient_name": display_name,
                "candidate_name": candidate_name or "the candidate",
                "round_name": round_name,
                "scheduled_at_label": scheduled_at_label,
                "form_url": link,
            },
        )
        email_service.send(to_email=employee.email.strip(), subject=subject, body=body, html=html)
    except Exception as exc:
        logger.warning("Background review mail failed for employee_id=%s: %s", employee_id, exc)
    finally:
        db.close()


def is_form_expired(form: Form) -> bool:
    return datetime.now(timezone.utc) > (form.last_sent_at + timedelta(hours=settings.FORM_EXPIRY_HOURS))
