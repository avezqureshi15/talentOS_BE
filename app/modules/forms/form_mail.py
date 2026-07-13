import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.common.email_templates import render_review_form_email, render_slot_form_email
from app.common.services.email_service import EmailService
from app.core.config import settings
from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.forms.form_model import Form
from app.modules.users.user_repository import UserRepository

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
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/book-slot/{form_id}"


def build_review_link(form_id: UUID) -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/rate-candidate/{form_id}"


def detail_to_message(detail: str) -> str:
    if detail == DETAIL_RESENT:
        return MSG_RESENT
    return MSG_NEW_LINK


def build_ask_summary_message(success_emp_ids: list[str]) -> str:
    if not success_emp_ids:
        return "No slot selection mails were queued."
    if len(success_emp_ids) == 1:
        return f"Slot selection mails are being sent to {success_emp_ids[0]}."
    joined = " and ".join(success_emp_ids)
    return f"Slot selection mails are being sent to {joined}."


def send_slot_mail_task(emp_id: str, form_id: UUID, is_reminder: bool = False) -> None:
    if not is_smtp_configured():
        logger.warning("Background mail skipped for emp_id=%s: SMTP not configured", emp_id)
        return

    db = SessionLocal()
    try:
        user_repo = UserRepository(db)
        user = user_repo.get_by_emp_id(emp_id)
        if not user:
            logger.warning("Background mail skipped: emp_id=%s not found", emp_id)
            return
        if not is_valid_email(user.email):
            logger.warning(
                "Background mail skipped for emp_id=%s: invalid or missing email",
                emp_id,
            )
            return

        display_name = user.name or emp_id
        link = build_slot_link(form_id)
        email_service = EmailService(
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
        )
        subject, body, html = render_slot_form_email(
            recipient_name=display_name,
            form_url=link,
            is_reminder=is_reminder,
        )
        email_service.send(to_email=user.email.strip(), subject=subject, body=body, html=html)
    except Exception as exc:
        logger.warning("Background mail failed for emp_id=%s: %s", emp_id, exc)
    finally:
        db.close()


def send_review_mail_task(
    emp_id: str,
    form_id: UUID,
    candidate_name: str | None = None,
    round_name: str | None = None,
    interviewer_name: str | None = None,
    is_reminder: bool = False,
) -> None:
    if not is_smtp_configured():
        logger.warning("Background review mail skipped for emp_id=%s: SMTP not configured", emp_id)
        return

    db = SessionLocal()
    try:
        user_repo = UserRepository(db)
        user = user_repo.get_by_emp_id(emp_id)
        if not user:
            logger.warning("Background review mail skipped: emp_id=%s not found", emp_id)
            return
        if not is_valid_email(user.email):
            logger.warning(
                "Background review mail skipped for emp_id=%s: invalid or missing email",
                emp_id,
            )
            return

        display_name = interviewer_name or user.name or emp_id
        link = build_review_link(form_id)
        email_service = EmailService(
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
        )
        subject, body, html = render_review_form_email(
            recipient_name=display_name,
            candidate_name=candidate_name or "the candidate",
            form_url=link,
            is_reminder=is_reminder,
        )
        email_service.send(to_email=user.email.strip(), subject=subject, body=body, html=html)
    except Exception as exc:
        logger.warning("Background review mail failed for emp_id=%s: %s", emp_id, exc)
    finally:
        db.close()


def is_form_expired(form: Form) -> bool:
    return datetime.now(timezone.utc) > (form.last_sent_at + timedelta(hours=settings.FORM_EXPIRY_HOURS))
