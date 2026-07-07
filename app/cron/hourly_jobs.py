import asyncio

from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.forms.form_service import FormService

logger = get_logger(__name__)

HOUR_SECONDS = 3600


def run_hourly_jobs_once() -> None:
    db = SessionLocal()
    try:
        service = FormService(db)
        reminders = service.run_reminder_job()
        escalations = service.run_escalation_job()
        reconciled = service.run_expiry_reconciliation_job()
        logger.info(
            "Hourly jobs done: reminders=%d escalations=%d reconciled=%d",
            reminders,
            escalations,
            reconciled,
        )
    finally:
        db.close()


async def run_hourly_jobs_forever(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            run_hourly_jobs_once()
        except Exception as exc:
            logger.warning("Hourly job loop failed: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=HOUR_SECONDS)
        except TimeoutError:
            continue
