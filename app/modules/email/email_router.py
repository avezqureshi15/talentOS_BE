from fastapi import APIRouter, HTTPException
from app.common.schemas.email_schema import SendEmailRequest, SendEmailResponse
from app.common.services.email_service import EmailService
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService(
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
        )
    return _email_service


router = APIRouter(prefix="/email", tags=["email"])


@router.post("/send", response_model=SendEmailResponse)
def send_email(body: SendEmailRequest):
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        raise HTTPException(status_code=500, detail="SMTP not configured")

    try:
        service = get_email_service()
        service.send(to_email=body.to_email, subject=body.subject, body=body.body)
        logger.info("Email sent to %s | subject=%s", body.to_email, body.subject)
        return SendEmailResponse(success=True, message="Email sent successfully")
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", body.to_email, exc)
        raise HTTPException(status_code=500, detail=str(exc))
