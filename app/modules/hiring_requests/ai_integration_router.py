import uuid
from datetime import datetime

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.ai_recruitment_client import AiRecruitmentClient
from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.rounds.round_model import Round

router = APIRouter(
    prefix="/api/v1/hiring-requests/{hiring_request_id}/ai",
    tags=["ai-integration"],
    dependencies=[Depends(require_permission(Permission.APPLICATION_VIEW))],
)


def _get_rh_job_id(hiring_request_id: str, db: Session) -> str:
    hr = db.query(HiringRequest).filter(HiringRequest.id == hiring_request_id).first()
    if not hr or not hr.rh_external_job_id:
        raise HTTPException(status_code=404, detail="No linked ai-recruitment-poc job found")
    return hr.rh_external_job_id


def _get_rh_candidate_id(candidate_id: int, db: Session) -> str:
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate or not candidate.rh_external_candidate_id:
        raise HTTPException(status_code=404, detail="No linked ai-recruitment-poc candidate found")
    return candidate.rh_external_candidate_id


@router.get("/screening/{candidate_id}")
async def get_screening_result(
    hiring_request_id: str,
    candidate_id: int,
    db: Session = Depends(get_db),
):
    rh_job_id = _get_rh_job_id(hiring_request_id, db)
    rh_candidate_id = _get_rh_candidate_id(candidate_id, db)
    client = AiRecruitmentClient()
    result = await client.get_screening_result(rh_job_id, rh_candidate_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Screening result not found")
    return result


@router.get("/candidates/{candidate_id}/interviews")
async def list_interviews(
    hiring_request_id: str,
    candidate_id: int,
    db: Session = Depends(get_db),
):
    rh_job_id = _get_rh_job_id(hiring_request_id, db)
    rh_candidate_id = _get_rh_candidate_id(candidate_id, db)
    client = AiRecruitmentClient()
    result = await client.list_interviews(rh_job_id, rh_candidate_id)
    if result is None:
        return []
    return result


@router.get("/candidates/{candidate_id}/interviews/{interview_id}")
async def get_interview_detail(
    hiring_request_id: str,
    candidate_id: int,
    interview_id: str,
    db: Session = Depends(get_db),
):
    rh_job_id = _get_rh_job_id(hiring_request_id, db)
    rh_candidate_id = _get_rh_candidate_id(candidate_id, db)
    client = AiRecruitmentClient()
    result = await client.get_interview_detail(rh_job_id, rh_candidate_id, interview_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Interview not found")
    return result


@router.get("/candidates")
async def list_ai_candidates(
    hiring_request_id: str,
    db: Session = Depends(get_db),
):
    rh_job_id = _get_rh_job_id(hiring_request_id, db)
    client = AiRecruitmentClient()
    result = await client.list_candidates(rh_job_id)
    if result is None:
        return []
    return result


class MoveToScreeningRequest(BaseModel):
    name: str
    email: str
    phone: str | None = None
    resume_url: str | None = None


@router.post("/candidates/{candidate_id}/move-to-screening", status_code=status.HTTP_202_ACCEPTED)
async def move_to_screening(
    hiring_request_id: str,
    candidate_id: int,
    body: MoveToScreeningRequest,
    db: Session = Depends(get_db),
):
    rh_job_id = _get_rh_job_id(hiring_request_id, db)
    client = AiRecruitmentClient()

    created = await client.create_candidate(
        job_id=rh_job_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        resume_url=body.resume_url,
    )
    if not created:
        raise HTTPException(status_code=502, detail="Failed to create candidate in ai-recruitment-poc")

    rh_candidate_id = created["id"]

    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if candidate:
        candidate.rh_external_candidate_id = rh_candidate_id
        db.commit()

    triggered = await client.trigger_screening(rh_job_id, rh_candidate_id)
    if not triggered:
        raise HTTPException(status_code=502, detail="Failed to trigger screening")

    return {
        "rh_candidate_id": rh_candidate_id,
        "screening_call_id": triggered.get("screening_call_id"),
        "status": triggered.get("status"),
    }


class TriggerInterviewRequest(BaseModel):
    round_name: str | None = None
    interview_type: str | None = "AI_INTERVIEW"
    round_type: str | None = "AI_INTERVIEW"
    scheduled_date: str | None = None
    scheduled_time: str | None = None
    scheduled_end_date: str | None = None
    scheduled_end_time: str | None = None


@router.post("/candidates/{candidate_id}/trigger-interview", status_code=status.HTTP_201_CREATED)
async def trigger_interview(
    hiring_request_id: str,
    candidate_id: int,
    body: TriggerInterviewRequest,
    db: Session = Depends(get_db),
):
    # FIXME: When ai-recruitment-poc service is up, remove this fallback.
    # The external POC call should create the interview and return an ID
    # that we link to our local round via rh_external_session_id.
    interview_id = None
    created = None
    try:
        rh_job_id = _get_rh_job_id(hiring_request_id, db)
        rh_candidate_id = _get_rh_candidate_id(candidate_id, db)
        client = AiRecruitmentClient()
        created = await client.trigger_interview(rh_job_id, rh_candidate_id, body.interview_type)
        if created:
            interview_id = created.get("id")
    except Exception:
        # POC unavailable — round created locally without external link
        pass

    def _parse_date(val: str | None):
        if not val:
            return None
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _parse_time(val: str | None):
        if not val:
            return None
        try:
            return datetime.strptime(val, "%H:%M").time()
        except ValueError:
            return None

    round_obj = Round(
        candidate_id=candidate_id,
        jd_id=uuid.UUID(hiring_request_id) if isinstance(hiring_request_id, str) else hiring_request_id,
        name=body.round_name or f"{body.round_type} Round",
        round_type=body.round_type,
        rh_external_session_id=interview_id,
        scheduled_date=_parse_date(body.scheduled_date),
        scheduled_time=_parse_time(body.scheduled_time),
        scheduled_end_date=_parse_date(body.scheduled_end_date),
        scheduled_end_time=_parse_time(body.scheduled_end_time),
    )
    db.add(round_obj)
    db.commit()
    db.refresh(round_obj)

    return {
        "round_id": str(round_obj.id),
        "rh_external_session_id": interview_id,
        "status": created.get("status") if created else "created_locally",
    }
