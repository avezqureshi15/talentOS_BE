import uuid

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.ai_recruitment_client import AiRecruitmentClient
from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.reviews.review_model import Review
from app.modules.rounds.round_model import Round
from app.modules.talentos_integration.talentos_result_service import (
    persist_interview_result,
    persist_screening_result,
)

router = APIRouter(
    prefix="/api/v1/hiring-requests/{hiring_request_id}/ai",
    tags=["ai-integration"],
    dependencies=[Depends(require_permission(Permission.APPLICATION_VIEW))],
)


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_time(val: str | None) -> time | None:
    if not val:
        return None
    try:
        return datetime.strptime(val, "%H:%M").time()
    except ValueError:
        return None


async def _get_or_create_rh_job(hiring_request_id: str, db: Session) -> str:
    hr = db.query(HiringRequest).filter(HiringRequest.id == hiring_request_id).first()
    if not hr:
        raise HTTPException(status_code=404, detail="Hiring request not found")

    if hr.rh_external_job_id:
        return hr.rh_external_job_id

    client = AiRecruitmentClient()
    created = await client.create_job(
        title=hr.title,
        description=hr.description,
        required_skills=hr.requirements,
        location=hr.location,
        department=hr.department,
        employment_type=hr.type,
    )
    if not created:
        raise HTTPException(status_code=502, detail="Failed to create job in ai-recruitment-poc")

    hr.rh_external_job_id = created["id"]
    db.commit()
    return created["id"]


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
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    rh_job_id = await _get_or_create_rh_job(hiring_request_id, db)
    rh_candidate_id = _get_rh_candidate_id(candidate_id, db)
    client = AiRecruitmentClient()
    result = await client.get_screening_result(rh_job_id, rh_candidate_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Screening result not found")

    if candidate.current_round_id:
        persist_screening_result(db, candidate.current_round_id, result)
    return result


@router.get("/candidates/{candidate_id}/interviews")
async def list_interviews(
    hiring_request_id: str,
    candidate_id: int,
    db: Session = Depends(get_db),
):
    rh_job_id = await _get_or_create_rh_job(hiring_request_id, db)
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
    rh_job_id = await _get_or_create_rh_job(hiring_request_id, db)
    rh_candidate_id = _get_rh_candidate_id(candidate_id, db)
    client = AiRecruitmentClient()
    result = await client.get_interview_detail(rh_job_id, rh_candidate_id, interview_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Interview not found")

    round_obj = db.query(Round).filter(Round.rh_external_session_id == interview_id).first()
    if round_obj:
        persist_interview_result(db, round_obj, result)
    return result


@router.get("/candidates")
async def list_ai_candidates(
    hiring_request_id: str,
    db: Session = Depends(get_db),
):
    rh_job_id = await _get_or_create_rh_job(hiring_request_id, db)
    client = AiRecruitmentClient()
    result = await client.list_candidates(rh_job_id)
    if result is None:
        return []
    return result


class MoveToAiScreeningRequest(BaseModel):
    force: bool = False
    round_name: str | None = None
    round_type: str | None = None
    scheduled_date: str | None = None
    scheduled_time: str | None = None
    scheduled_end_date: str | None = None
    scheduled_end_time: str | None = None


@router.post("/candidates/{candidate_id}/move-to-screening", status_code=status.HTTP_202_ACCEPTED)
async def move_to_ai_screening(
    hiring_request_id: str,
    candidate_id: int,
    body: MoveToAiScreeningRequest,
    db: Session = Depends(get_db),
):
    hr = db.query(HiringRequest).filter(HiringRequest.id == hiring_request_id).first()
    if not hr:
        raise HTTPException(status_code=404, detail="Hiring request not found")

    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    try:
        client = AiRecruitmentClient()
        result = await client.create_candidate_with_screening(
            external_job_id=str(hr.id),
            name=candidate.candidate_name or "Unknown",
            email=candidate.candidate_email or "",
            phone=candidate.candidate_phone,
            external_candidate_id=str(candidate.id),
            force=body.force,
        )

        if not result:
            raise HTTPException(status_code=502, detail="Failed to move candidate to AI screening")

        round_obj = Round(
            candidate_id=candidate.id,
            jd_id=hr.id,
            name=body.round_name or "AI Screening Round",
            round_type=body.round_type or "AI_SCREENING_ROUND",
            scheduled_date=_parse_date(body.scheduled_date),
            scheduled_time=_parse_time(body.scheduled_time),
            scheduled_end_date=_parse_date(body.scheduled_end_date),
            scheduled_end_time=_parse_time(body.scheduled_end_time),
        )
        db.add(round_obj)
        db.flush()

        db.add(Review(
            round_id=round_obj.id,
            entity_type="ai_screening",
            reviews={
                "status": "queued",
                "screening_call_id": result.get("screening_call_id"),
            },
        ))

        candidate.rh_external_candidate_id = result["candidate"]["id"]
        candidate.rh_external_screening_call_id = result.get("screening_call_id")
        candidate.current_round_id = round_obj.id
        candidate.status = "SCREENING_ROUND_SCHEDULED"
        candidate.stage = "AI_SCREENING"
        db.commit()
    except Exception:
        db.rollback()
        raise

    return result


class MoveToAiInterviewRequest(BaseModel):
    force: bool = False
    interview_type: str | None = "AI_INTERVIEW"
    round_name: str | None = None
    round_type: str | None = None
    scheduled_date: str | None = None
    scheduled_time: str | None = None
    scheduled_end_date: str | None = None
    scheduled_end_time: str | None = None


@router.post("/candidates/{candidate_id}/move-to-interview", status_code=status.HTTP_201_CREATED)
async def move_to_ai_interview(
    hiring_request_id: str,
    candidate_id: int,
    body: MoveToAiInterviewRequest,
    db: Session = Depends(get_db),
):
    hr = db.query(HiringRequest).filter(HiringRequest.id == hiring_request_id).first()
    if not hr:
        raise HTTPException(status_code=404, detail="Hiring request not found")

    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    try:
        client = AiRecruitmentClient()
        result = await client.create_candidate_with_interview(
            external_job_id=str(hr.id),
            name=candidate.candidate_name or "Unknown",
            email=candidate.candidate_email or "",
            phone=candidate.candidate_phone,
            external_candidate_id=str(candidate.id),
            force=body.force,
            interview_type=body.interview_type,
        )

        if not result:
            raise HTTPException(status_code=502, detail="Failed to move candidate to AI interview")

        interview = result.get("interview") or {}
        interview_url = interview.get("interview_url")
        unique_token = interview_url.rsplit("/", 1)[-1] if interview_url else None

        round_obj = Round(
            candidate_id=candidate.id,
            jd_id=hr.id,
            name=body.round_name or f"{body.round_type or 'AI_INTERVIEW'} Round",
            round_type=body.round_type or "AI_INTERVIEW_ROUND",
            rh_external_session_id=interview.get("id"),
            rh_interview_url=interview_url,
            rh_unique_token=unique_token,
            scheduled_date=_parse_date(body.scheduled_date),
            scheduled_time=_parse_time(body.scheduled_time),
            scheduled_end_date=_parse_date(body.scheduled_end_date),
            scheduled_end_time=_parse_time(body.scheduled_end_time),
        )
        db.add(round_obj)
        db.flush()

        db.add(Review(
            round_id=round_obj.id,
            entity_type="ai_interview",
            reviews={
                "status": interview.get("status") or "pending",
                "interview_url": interview_url,
                "unique_token": unique_token,
            },
        ))

        candidate.rh_external_candidate_id = result["candidate"]["id"]
        candidate.current_round_id = round_obj.id
        candidate.status = "INTERVIEW_SCHEDULED"
        candidate.stage = "AI_INTERVIEW"
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "round_id": str(round_obj.id),
        "rh_external_session_id": interview.get("id"),
        "interview_url": interview_url,
        "candidate": result.get("candidate"),
        "status": "created",
    }


_SCREENING_KEYS = [
    "call_status", "call_outcome", "ended_reason", "retry_count", "result",
    "summary", "transcript", "availability", "employment_status",
    "relevant_experience", "current_ctc", "expected_ctc", "notice_period",
    "location_preference", "communication_quality", "willingness_to_proceed",
    "created_at",
]

_INTERVIEW_KEYS = [
    "status", "transcript", "summary", "transcript_summary",
    "overall_score", "technical_fit_score", "communication_score",
    "problem_solving_score", "experience_score", "role_alignment_score",
    "strengths", "weaknesses", "jd_fit", "final_recommendation",
    "interview_url", "created_at", "started_at", "completed_at",
]


@router.post("/retry-screening/{candidate_id}")
async def retry_ai_screening(
    hiring_request_id: str,
    candidate_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission(Permission.APPLICATION_WORKFLOW)),
):
    """Re-pull the AI screening result from the POC and re-persist it."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if not candidate.current_round_id:
        raise HTTPException(
            status_code=409, detail="Candidate has no AI screening round to retry"
        )

    rh_job_id = await _get_or_create_rh_job(hiring_request_id, db)
    rh_candidate_id = _get_rh_candidate_id(candidate_id, db)
    client = AiRecruitmentClient()
    result = await client.get_screening_result(rh_job_id, rh_candidate_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail="No screening result available in ai-recruitment-poc"
        )

    persist_screening_result(db, candidate.current_round_id, result)
    db.commit()

    missing = [k for k in _SCREENING_KEYS if result.get(k) is None]
    return {
        "status": "ok",
        "round_id": str(candidate.current_round_id),
        "entity_type": "ai_screening",
        "result_found": True,
        "missing_fields": missing,
    }


@router.post("/retry-interview/{candidate_id}")
async def retry_ai_interview(
    hiring_request_id: str,
    candidate_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission(Permission.APPLICATION_WORKFLOW)),
):
    """Re-pull the latest AI interview detail from the POC and re-persist it."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    rh_job_id = await _get_or_create_rh_job(hiring_request_id, db)
    rh_candidate_id = _get_rh_candidate_id(candidate_id, db)
    client = AiRecruitmentClient()
    interviews = await client.list_interviews(rh_job_id, rh_candidate_id)
    if not interviews:
        raise HTTPException(
            status_code=404, detail="No AI interview found in ai-recruitment-poc"
        )

    latest = interviews[0]
    interview_id = latest.get("id")
    result = await client.get_interview_detail(rh_job_id, rh_candidate_id, interview_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail="No interview result available in ai-recruitment-poc"
        )

    round_obj = (
        db.query(Round).filter(Round.rh_external_session_id == interview_id).first()
    )
    if round_obj is None and candidate.current_round_id:
        round_obj = db.query(Round).filter(Round.id == candidate.current_round_id).first()

    if round_obj is None:
        raise HTTPException(
            status_code=409, detail="No AI interview round linked to this candidate"
        )

    persist_interview_result(db, round_obj, result)
    db.commit()

    missing = [k for k in _INTERVIEW_KEYS if result.get(k) is None]
    return {
        "status": "ok",
        "round_id": str(round_obj.id),
        "entity_type": "ai_interview",
        "result_found": True,
        "missing_fields": missing,
    }


@router.get("/candidates/{candidate_id}/interviews/{interview_id}/recording-url")
async def get_interview_recording_url(
    hiring_request_id: str,
    candidate_id: int,
    interview_id: str,
    db: Session = Depends(get_db),
):
    """Fetch a fresh presigned URL for the interview recording from the POC."""
    rh_job_id = await _get_or_create_rh_job(hiring_request_id, db)
    rh_candidate_id = _get_rh_candidate_id(candidate_id, db)
    client = AiRecruitmentClient()
    url = await client.get_interview_recording_url(rh_job_id, rh_candidate_id, interview_id)
    return {"recording_url": url}

