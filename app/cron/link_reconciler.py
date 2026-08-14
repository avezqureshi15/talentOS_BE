"""Periodic sweep that advances the POC ↔ talentOS connect handshake on the
talentOS side.

After provisioning (keys exchanged) the POC's reconciler drives most of the
lifecycle; this job guarantees progress when the POC is slow or temporarily down:

- Claim TRANSIENT connect/disconnect flows whose ``next_retry_at`` is due with
  ``FOR UPDATE SKIP LOCKED`` (no two workers act on the same flow).
- ping_a (talentOS → POC, rhub_ key): talentOS proves its outbound credential.
  If the POC has already pinged us (ping_b), the flow becomes ``linked``.
- Enforce the retry budget: flows that burn all attempts are failed (tal_ and
  peer key revoked, transient plaintext cleared) — ``cleanup_expired`` catches
  the crash leftovers the per-flow path never sees.
"""

import asyncio
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from sqlalchemy import select

from app.core.config import settings
from app.core.logger import get_logger
from app.cron.retry import with_cron_retry
from app.db.session import SessionLocal
from app.modules.talentos_integration.connections_service import (
    MAX_ATTEMPTS,
    ConnectionsService,
)
from app.modules.talentos_integration.integration_link_model import (
    IntegrationLinkFlow,
    TRANSIENT_STATES,
    utcnow,
)

logger = get_logger(__name__)

JOB_ID = "link_reconciler_sweep"
JOB_NAME = "POC Integration Link Reconciler"
BATCH_SIZE = 50


def _cron_trigger() -> IntervalTrigger | CronTrigger:
    if settings.APP_ENV in ("development", "uat", "staging"):
        return IntervalTrigger(seconds=10)
    return IntervalTrigger(minutes=1)


async def _sweep_once(db) -> int:
    service = ConnectionsService(db)
    now = utcnow()

    flows = (
        db.execute(
            select(IntegrationLinkFlow)
            .where(
                IntegrationLinkFlow.state.in_(TRANSIENT_STATES),
                IntegrationLinkFlow.next_retry_at <= now,
                IntegrationLinkFlow.attempts < MAX_ATTEMPTS,
            )
            .order_by(IntegrationLinkFlow.next_retry_at)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        .scalars()
        .all()
    )

    for flow in flows:
        try:
            outcome = await service.reconcile_flow(flow)
            db.commit()
            logger.info(
                "link_reconciler | flow_id=%s operation=%s state=%s outcome=%s",
                flow.flow_id, flow.operation, flow.state, outcome,
            )
        except Exception as exc:  # must not strand the sweep on one bad flow
            db.rollback()
            logger.warning(
                "link_reconciler error | flow_id=%s err=%s", flow.flow_id, exc,
            )

    try:
        failed = service.cleanup_expired()
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("link_reconciler cleanup error: %s", exc)
        failed = 0
    return len(flows) + failed


def _run_sweep() -> None:
    started = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        count = asyncio.run(_sweep_once(db))
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info(
            "link_reconciler_sweep completed | count=%d elapsed_seconds=%.2f",
            count, elapsed,
        )
    finally:
        db.close()


def _run_sweep_with_retry() -> None:
    with_cron_retry(
        job_id=JOB_ID,
        fn=_run_sweep,
        max_attempts=3,
        job_name=JOB_NAME,
        trigger="interval",
    )


def setup_link_reconciler(scheduler: BackgroundScheduler) -> None:
    scheduler.add_job(
        _run_sweep_with_retry,
        trigger=_cron_trigger(),
        id=JOB_ID,
        replace_existing=True,
        name=JOB_NAME,
    )
    job = scheduler.get_job(JOB_ID)
    if job:
        logger.info(
            "Registered cron job | id=%s name=\"%s\" next_run=%s trigger=%s",
            job.id, job.name, getattr(job, "next_run_time", None), job.trigger,
        )