"""Send AI-interview invite emails. Best-effort — never blocks the round transaction."""

from __future__ import annotations

import re

from app.common.services.email_service import EmailService
from app.core.config import settings
from app.core.logger import get_logger
from app.modules.hiring_requests.ai_interview_mail_templates import (
    render_interview_invite_email,
)

logger = get_logger(__name__)

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_valid_email(email: str | None) -> bool:
    return bool(email and _EMAIL_PATTERN.match(email.strip()))


def _is_smtp_configured() -> bool:
    return bool(settings.SMTP_USERNAME.strip() and settings.SMTP_PASSWORD.strip())


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

    subject, body, html = render_interview_invite_email(
        candidate_name=(candidate_name or "there").strip(),
        role_title=(role_title or "the role").strip(),
        interview_url=interview_url,
    )
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
        logger.warning("Interview invite send failed for %s: %s", candidate_email, exc)
        return False
