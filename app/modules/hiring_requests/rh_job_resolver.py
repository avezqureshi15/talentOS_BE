"""Shared helper to resolve (and self-heal) the POC job id for a hiring request.

The POC's ``POST /internal/talentos/jobs`` is idempotent on ``external_job_id``
+ tenant: it returns the existing job when one matches, otherwise it creates a
new one. This makes it a safe way to recover from a stale/missing
``hiring_requests.rh_external_job_id`` (e.g. after a POC DB reset) — the call
always converges to the canonical POC job id for the caller's tenant.
"""

import logging

from sqlalchemy.orm import Session

from app.core.ai_recruitment_client import AiRecruitmentClient
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.hiring_requests.location_utils import format_locations

logger = logging.getLogger(__name__)


async def resolve_or_create_rh_job(db: Session, hr: HiringRequest) -> str | None:
    """Return the canonical POC job id for ``hr``, creating it if needed.

    Also reconciles ``hr.rh_external_job_id`` in the DB whenever the POC's
    answer differs from what's stored (idempotent create -> existing job or a
    fresh one scoped to the caller's tenant). Returns ``None`` when the POC is
    unreachable or rejects the request.
    """
    client = AiRecruitmentClient(tenant_id=hr.tenant_id)
    created = await client.create_job(
        title=hr.title,
        description=hr.description,
        required_skills=hr.requirements,
        location=format_locations(hr.location),
        department=hr.department,
        employment_type=hr.type,
        external_job_id=str(hr.id),
    )
    if not isinstance(created, dict) or not created.get("id"):
        logger.warning(
            "RH job resolve failed for hiring request %s (tenant=%s)",
            hr.id, hr.tenant_id,
        )
        return None

    job_id = str(created["id"])
    if hr.rh_external_job_id != job_id:
        logger.info(
            "RH job id reconciled for hiring request %s: %s -> %s",
            hr.id, hr.rh_external_job_id, job_id,
        )
        hr.rh_external_job_id = job_id
        db.commit()
    return job_id
