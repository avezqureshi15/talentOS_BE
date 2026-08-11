from app.core.config import settings
from app.core.frontend import build_frontend_link
from app.core.logger import get_logger
from app.common.services.email_service import EmailService
from app.db.session import SessionLocal
from app.modules.email.email_template_service import render as render_email_template

logger = get_logger(__name__)


def send_invite_email(
    email: str,
    token: str,
    *,
    organization_name: str | None = None,
    inviter_name: str | None = None,
) -> None:
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        logger.warning("SMTP not configured — skipping invite email to %s", email)
        return
    try:
        service = EmailService(
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
        )
        link = build_frontend_link(f"/auth/invite/{token}")
        db = SessionLocal()
        try:
            subject, body, html = render_email_template(
                db,
                "invite",
                {
                    "recipient_email": email,
                    "organization_name": organization_name,
                    "inviter_name": inviter_name,
                    "link": link,
                },
            )
        finally:
            db.close()
        service.send(to_email=email, subject=subject, body=body, html=html)
    except Exception as exc:
        logger.warning("Failed to send invite email to %s: %s", email, exc)
