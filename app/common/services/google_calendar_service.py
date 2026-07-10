from datetime import datetime, timezone
from uuid import uuid4

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def _to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class GoogleCalendarService:
    def __init__(
        self,
        *,
        service_account_path: str,
        impersonation_email: str,
        timezone: str,
    ):
        self.service_account_path = service_account_path
        self.impersonation_email = impersonation_email
        self.timezone = timezone

    def create_meet(
        self,
        *,
        title: str,
        start: datetime,
        end: datetime,
        attendees: list[str],
        description: str = "",
        with_gmeet: bool = True,
    ) -> dict[str, str | None]:
        logger.info(
            "Creating calendar event: title=%s | attendees=%d | gmeet=%s",
            title, len(attendees), with_gmeet,
        )
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_path,
                scopes=[_CALENDAR_SCOPE],
                subject=self.impersonation_email,
            )
            service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

            body: dict = {
                "summary": title,
                "description": description,
                "start": {
                    "dateTime": _to_rfc3339(start),
                    "timeZone": self.timezone,
                },
                "end": {
                    "dateTime": _to_rfc3339(end),
                    "timeZone": self.timezone,
                },
                "attendees": [{"email": email} for email in attendees],
            }
            insert_kwargs: dict = {
                "calendarId": "primary",
                "sendUpdates": "all",
                "body": body,
            }
            if with_gmeet:
                body["conferenceData"] = {
                    "createRequest": {
                        "requestId": str(uuid4()),
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                }
                insert_kwargs["conferenceDataVersion"] = 1

            event = service.events().insert(**insert_kwargs).execute()

            meet_link: str | None = None
            if with_gmeet:
                meet_link = next(
                    (
                        ep["uri"]
                        for ep in event.get("conferenceData", {}).get("entryPoints", [])
                        if ep.get("entryPointType") == "video"
                    ),
                    None,
                )

            logger.info("Calendar event created: id=%s | meet_link=%s", event["id"], meet_link)
            return {
                "event_id": event["id"],
                "meet_link": meet_link,
                "calendar_link": event.get("htmlLink", ""),
            }
        except Exception:
            logger.exception("Failed to create calendar event: title=%s", title)
            raise
