"""Webhook endpoints receiving screening/interview completion pushes from ai-recruitment-poc.

Auth: the same service API key used by the other /internal endpoints
(verify_service_api_key). The POC sends a Bearer token with TALENTOS_BE_API_KEY.
"""

from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.service_auth import verify_service_api_key
from app.db.session import get_db
from app.modules.talentos_integration.talentos_result_service import (
    handle_interview_webhook,
    handle_screening_webhook,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/internal/talentos/webhooks",
    tags=["talentos-webhooks"],
    dependencies=[Depends(verify_service_api_key)],
)


class TalentosScreeningWebhookBody(BaseModel):
    external_job_id: str | None = None
    external_candidate_id: str | None = None
    screening_call_id: str | None = None
    result: dict = {}


class TalentosInterviewWebhookBody(BaseModel):
    external_job_id: str | None = None
    external_candidate_id: str | None = None
    interview_id: str | None = None
    result: dict = {}


@router.post("/screening", status_code=status.HTTP_202_ACCEPTED)
def talentos_screening_completed(
    body: TalentosScreeningWebhookBody,
    db: Session = Depends(get_db),
):
    try:
        outcome = handle_screening_webhook(db, body.model_dump())
        db.commit()
        logger.info(
            "talentOS screening webhook processed: status=%s call_id=%s",
            outcome.get("status"),
            body.screening_call_id,
        )
        return outcome
    except Exception:
        db.rollback()
        raise


@router.post("/interview", status_code=status.HTTP_202_ACCEPTED)
def talentos_interview_completed(
    body: TalentosInterviewWebhookBody,
    db: Session = Depends(get_db),
):
    try:
        outcome = handle_interview_webhook(db, body.model_dump())
        db.commit()
        logger.info(
            "talentOS interview webhook processed: status=%s interview_id=%s",
            outcome.get("status"),
            body.interview_id,
        )
        return outcome
    except Exception:
        db.rollback()
        raise
