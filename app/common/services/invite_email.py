from app.core.config import settings
from app.core.frontend import build_frontend_link
from app.core.logger import get_logger
from app.common.services.email_service import EmailService

logger = get_logger(__name__)


def send_invite_email(email: str, token: str) -> None:
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
        subject = "You're invited to join TalentOS"
        body = f"""Hello,

You have been invited to join TalentOS. Click the link below to set up your account:

{link}

This invite expires in 7 days.

If you did not expect this invitation, you can ignore this email.

Best,
The TalentOS Team"""
        html = f"""<p>Hello,</p>
<p>You have been invited to join <strong>TalentOS</strong>. Click the button below to set up your account:</p>
<p style="text-align:center;margin:24px 0">
  <a href="{link}" style="display:inline-block;padding:12px 24px;background:#ffffff;color:#000000;text-decoration:none;border-radius:8px;font-weight:600">Accept Invite</a>
</p>
<p>This invite expires in 7 days.</p>
<p>If you did not expect this invitation, you can ignore this email.</p>
<p>Best,<br>The TalentOS Team</p>"""
        service.send(to_email=email, subject=subject, body=body, html=html)
    except Exception as exc:
        logger.warning("Failed to send invite email to %s: %s", email, exc)
