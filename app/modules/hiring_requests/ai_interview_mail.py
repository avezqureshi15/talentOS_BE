"""Send AI-interview invite emails. Best-effort — never blocks the round transaction."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from app.common.services.email_service import EmailService
from app.core.config import settings
from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.email.email_template_service import render as render_email_template

logger = get_logger(__name__)

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_valid_email(email: str | None) -> bool:
    return bool(email and _EMAIL_PATTERN.match(email.strip()))


def _is_smtp_configured() -> bool:
    return bool(settings.SMTP_USERNAME.strip() and settings.SMTP_PASSWORD.strip())


def _send_interview_mail(
    candidate_email: str,
    subject: str,
    body: str,
    html: str,
) -> bool:
    """Return True on send-success, False if skipped or failed.

    Never raises: the caller does not care about SMTP outcomes at commit time.
    """
    if not _is_valid_email(candidate_email):
        logger.warning("Interview mail skipped: invalid candidate email %r", candidate_email)
        return False
    if not _is_smtp_configured():
        logger.warning("Interview mail skipped: SMTP not configured")
        return False

    try:
        EmailService(
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
        ).send(
            to_email=candidate_email.strip(),
            subject=subject,
            body=body,
            html=html,
        )
        return True
    except Exception as exc:
        logger.warning("Interview mail send failed for %s: %s", candidate_email, exc)
        return False


def send_interview_invite_email(
    candidate_email: str | None,
    candidate_name: str | None,
    role_title: str | None,
    interview_url: str | None,
) -> bool:
    """Return True on send-success, False if skipped or failed.

    Never raises: the caller does not care about SMTP outcomes at commit time.
    """
    if not interview_url:
        logger.warning("Interview invite skipped: no interview_url")
        return False
    if not _is_valid_email(candidate_email):
        logger.warning("Interview invite skipped: invalid candidate email %r", candidate_email)
        return False
    if not _is_smtp_configured():
        logger.warning("Interview invite skipped: SMTP not configured")
        return False

    db = SessionLocal()
    try:
        subject, body, html = render_email_template(
            db,
            "interview_invite",
            {
                "candidate_name": (candidate_name or "there").strip(),
                "role_title": (role_title or "the role").strip(),
                "interview_url": interview_url,
            },
        )
    finally:
        db.close()
    return _send_interview_mail(candidate_email, subject, body, html)


def format_scheduled_slot_label(
    scheduled_date: str | None,
    scheduled_time: str | None,
    timezone: str | None,
) -> str:
    """Human-readable slot label, e.g. 'Monday, 21 July 2026 at 4:00 PM IST'."""
    if not scheduled_date or not scheduled_time:
        return ""
    try:
        tz = ZoneInfo(timezone or "Asia/Kolkata")
    except Exception:
        tz = ZoneInfo("Asia/Kolkata")
    dt = datetime.fromisoformat(f"{scheduled_date}T{scheduled_time}").replace(tzinfo=tz)
    label = dt.strftime("%A, %d %B %Y at %I:%M %p").replace(" 0", " ")
    tz_name = dt.tzname() or ""
    return f"{label} {tz_name}".rstrip()


def send_interview_slot_email(
    candidate_email: str | None,
    candidate_name: str | None,
    role_title: str | None,
    interview_url: str | None,
    scheduled_at_label: str | None,
) -> bool:
    """Send a 'scheduled for <slot>' email. Best-effort like the invite mail."""
    if not interview_url or not scheduled_at_label:
        logger.warning("Interview slot email skipped: missing url or slot label")
        return False
    if not _is_valid_email(candidate_email):
        logger.warning("Interview slot email skipped: invalid candidate email %r", candidate_email)
        return False
    if not _is_smtp_configured():
        logger.warning("Interview slot email skipped: SMTP not configured")
        return False

    db = SessionLocal()
    try:
        subject, body, html = render_email_template(
            db,
            "interview_slot",
            {
                "candidate_name": (candidate_name or "there").strip(),
                "role_title": (role_title or "the role").strip(),
                "interview_url": interview_url,
                "scheduled_at_label": scheduled_at_label,
            },
        )
    finally:
        db.close()
    return _send_interview_mail(candidate_email, subject, body, html)
