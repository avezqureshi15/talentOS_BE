import uuid
from datetime import time
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.ai_recruitment_client import AiRecruitmentClient
from app.modules.call_windows.call_window_schema import (
    CallWindowResponse,
    CallWindowUpdate,
)
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.interview_designs.interview_design_service import _resolve_rh_job

_DEFAULT_TIMEZONE = "Asia/Kolkata"
_POC_SYNC_ERROR = "ai-recruitment-poc unreachable — showing defaults"
_POC_JOB_CREATE_ERROR = "Failed to create linked job in ai-recruitment-poc"


def _get_hiring_request(hiring_request_id: str, db: Session) -> HiringRequest:
    try:
        parsed = uuid.UUID(hiring_request_id)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=404, detail="Hiring request not found") from exc
    hiring_request = (
        db.query(HiringRequest).filter(HiringRequest.id == parsed).first()
    )
    if not hiring_request:
        raise HTTPException(status_code=404, detail="Hiring request not found")
    return hiring_request


def _time_value(value: Optional[time]) -> Optional[str]:
    return str(value) if value is not None else None


def _from_poc(result: dict, hiring_request_id: str, errors: list[str]) -> CallWindowResponse:
    return CallWindowResponse(
        hiring_request_id=uuid.UUID(hiring_request_id),
        screening_call_from=result.get("screening_call_from") or None,
        screening_call_to=result.get("screening_call_to") or None,
        screening_timezone=result.get("screening_timezone") or _DEFAULT_TIMEZONE,
        sync_status="synced" if not errors else "draft",
        sync_errors=errors,
    )


async def get_call_window(hiring_request_id: str, db: Session) -> CallWindowResponse:
    hiring_request = _get_hiring_request(hiring_request_id, db)

    errors: list[str] = []
    try:
        rh_job_id = await _resolve_rh_job(hiring_request, db)
        result = await AiRecruitmentClient().get_call_window(
            rh_job_id,
            external_job_id=str(hiring_request.id),
        )
    except HTTPException:
        errors.append(_POC_JOB_CREATE_ERROR)
        result = None

    if result is None:
        errors.append(_POC_SYNC_ERROR)
        return _from_poc({}, hiring_request_id, errors)

    return _from_poc(result, hiring_request_id, errors)


async def update_call_window(
    hiring_request_id: str,
    body: CallWindowUpdate,
    db: Session,
) -> CallWindowResponse:
    hiring_request = _get_hiring_request(hiring_request_id, db)

    try:
        rh_job_id = await _resolve_rh_job(hiring_request, db)
        updates = body.model_dump(exclude_unset=True)
        result = await AiRecruitmentClient().update_call_window(
            rh_job_id,
            screening_call_from=_time_value(updates.get("screening_call_from")),
            screening_call_to=_time_value(updates.get("screening_call_to")),
            screening_timezone=updates.get("screening_timezone"),
            external_job_id=str(hiring_request.id),
        )
        if result is None:
            raise HTTPException(status_code=502, detail=_POC_SYNC_ERROR)
    except HTTPException:
        raise

    return _from_poc(result, hiring_request_id, [])
