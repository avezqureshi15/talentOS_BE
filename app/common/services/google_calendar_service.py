from datetime import datetime, timezone
from uuid import uuid4

from google.api_core.exceptions import GoogleAPICallError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.common.schemas.calendar_schema import CalendarEventResponse
from app.core.logger import get_logger

logger = get_logger(__name__)

_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
_RETRIES = 3


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
        self._credentials: service_account.Credentials | None = None
        self._service: object | None = None

    def _get_credentials(self) -> service_account.Credentials:
        if self._credentials is None:
            self._credentials = service_account.Credentials.from_service_account_file(
                self.service_account_path,
                scopes=[_CALENDAR_SCOPE],
                subject=self.impersonation_email,
            )
        return self._credentials

    def _get_service(self):
        if self._service is None:
            credentials = self._get_credentials()
            self._service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        return self._service

    def create_meet(
        self,
        *,
        title: str,
        start: datetime,
        end: datetime,
        attendees: list[str],
        description: str = "",
        with_gmeet: bool = True,
    ) -> CalendarEventResponse:
        logger.info(
            "Creating calendar event: title=%s | attendees=%d | gmeet=%s",
            title, len(attendees), with_gmeet,
        )
        try:
            service = self._get_service()

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

            event = service.events().insert(**insert_kwargs).execute(num_retries=_RETRIES)

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
            return CalendarEventResponse(
                event_id=event["id"],
                meet_link=meet_link,
                calendar_link=event.get("htmlLink", ""),
            )
        except (HttpError, GoogleAPICallError) as exc:
            logger.exception("Google Calendar API failed: title=%s", title)
            raise
        except Exception:
            logger.exception("Unexpected error creating calendar event: title=%s", title)
            raise

    def update_event(
        self,
        *,
        event_id: str,
        title: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        attendees: list[str] | None = None,
        description: str | None = None,
        with_gmeet: bool = True,
    ) -> CalendarEventResponse:
        logger.info("Updating calendar event: event_id=%s", event_id)
        try:
            service = self._get_service()
            body: dict = {}

            if title is not None:
                body["summary"] = title
            if start is not None:
                body["start"] = {"dateTime": _to_rfc3339(start), "timeZone": self.timezone}
            if end is not None:
                body["end"] = {"dateTime": _to_rfc3339(end), "timeZone": self.timezone}
            if attendees is not None:
                body["attendees"] = [{"email": email} for email in attendees]
            if description is not None:
                body["description"] = description
            if with_gmeet and "conferenceData" not in body:
                body["conferenceData"] = {
                    "createRequest": {
                        "requestId": str(uuid4()),
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                }

            event = (
                service.events()
                .patch(calendarId="primary", eventId=event_id, body=body, sendUpdates="all")
                .execute(num_retries=_RETRIES)
            )

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

            logger.info("Calendar event updated: id=%s | meet_link=%s", event["id"], meet_link)
            return CalendarEventResponse(
                event_id=event["id"],
                meet_link=meet_link,
                calendar_link=event.get("htmlLink", ""),
            )
        except HttpError as exc:
            if exc.resp.status == 410:
                logger.warning("Calendar event already deleted, cannot update: event_id=%s", event_id)
                return CalendarEventResponse(event_id=event_id, meet_link=None, calendar_link="")
            logger.exception("Google Calendar API failed: event_id=%s", event_id)
            raise
        except GoogleAPICallError:
            logger.exception("Google Calendar API failed: event_id=%s", event_id)
            raise
        except Exception:
            logger.exception("Unexpected error updating calendar event: event_id=%s", event_id)
            raise

    def cancel_event(self, *, event_id: str) -> None:
        logger.info("Cancelling calendar event: event_id=%s", event_id)
        try:
            service = self._get_service()
            service.events().delete(calendarId="primary", eventId=event_id, sendUpdates="all").execute(
                num_retries=_RETRIES
            )
            logger.info("Calendar event cancelled: event_id=%s", event_id)
        except HttpError as exc:
            if exc.resp.status == 410:
                logger.warning("Calendar event already deleted: event_id=%s", event_id)
                return
            logger.exception("Google Calendar API failed: event_id=%s", event_id)
            raise
        except GoogleAPICallError:
            logger.exception("Google Calendar API failed: event_id=%s", event_id)
            raise
        except Exception:
            logger.exception("Unexpected error cancelling calendar event: event_id=%s", event_id)
            raise
