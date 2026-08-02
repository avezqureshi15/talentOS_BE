"""MeetMind HTTP client — register Google Meet interviews for transcription.

Schedule auth: X-API-Key shared secret.
Webhook (inbound) uses X-Signature HMAC separately; not used here.

Schedule body: meetUrl, platform, title, participantEmails, external.
"""

from app.common.clients.base_client import BaseClient, ClientError
from app.core.config import settings
from app.core.constants import ErrorCode
from app.core.logger import get_logger
from app.core.secrets import get_secret

logger = get_logger(__name__)


class MeetMindClientError(ClientError):
    """Raised when MeetMind returns an error or is unreachable."""


class MeetMindClient(BaseClient):
    """Client for MeetMind POST /api/integrations/schedule."""

    def __init__(self) -> None:
        super().__init__(
            base_url=settings.MEETMIND_BASE_URL,
            timeout=30,
            max_retries=2,
        )

    @property
    def _service_name(self) -> str:
        return "MeetMind"

    def schedule_meeting(
        self,
        meet_url: str,
        title: str,
        participant_emails: list[str],
    ) -> bool:
        """Register a meeting with MeetMind. Returns True on success, False if skipped/failed.

        Does not raise to callers for booking-path best-effort use — logs and returns False.
        """
        if not settings.MEETMIND_BASE_URL:
            logger.warning("MeetMind schedule skipped | MEETMIND_BASE_URL unset")
            return False
        api_token = get_secret("MEETMIND_API_TOKEN")
        if not api_token:
            logger.warning("MeetMind schedule skipped | MEETMIND_API_TOKEN unset")
            return False
        if not meet_url:
            logger.warning("MeetMind schedule skipped | empty meet_url")
            return False

        body = {
            "meetUrl": meet_url,
            "platform": "google-meet",
            "title": title,
            "participantEmails": participant_emails,
            "external": settings.MEETMIND_EXTERNAL,
        }
        headers = {"X-API-Key": api_token}
        try:
            self._post("api/integrations/schedule", json_data=body, headers=headers)
            logger.info("MeetMind schedule succeeded | meet_url=%s title=%s", meet_url, title)
            return True
        except Exception:
            logger.exception("MeetMind schedule failed | meet_url=%s", meet_url)
            return False

    def _map_error(self, exc: Exception) -> Exception:
        from httpx import HTTPStatusError

        if isinstance(exc, HTTPStatusError):
            status = exc.response.status_code
            try:
                body = exc.response.json()
                detail = body.get("error", body.get("message", str(body)))
            except Exception:
                detail = exc.response.text[:200]
            return MeetMindClientError(
                message=f"MeetMind returned {status}: {detail}",
                code=ErrorCode.INTERNAL_ERROR,
                status_code=status,
            )
        return MeetMindClientError(
            message=f"MeetMind unreachable: {exc}",
            code=ErrorCode.INTERNAL_ERROR,
            status_code=502,
        )
