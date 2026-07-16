from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.applications.application_schema import (
    ApplicationCreate,
    EvaluatedCandidate,
    FinalVerdictUpdate,
    PaginatedEvaluatedCandidatesResponse,
)
from app.modules.applications.application_service import ApplicationService
from app.modules.evaluations.evaluation_schema import EvaluationResponse

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/applications", tags=["applications"])


@router.get("/final-verdicts", response_model=PaginatedEvaluatedCandidatesResponse)
def get_finalized_candidates(
    candidate_status: str | None = Query(default=None, description="Filter by final verdict (selected, rejected)"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    service = ApplicationService(db)
    return service.get_finalized_candidates_paginated(
        verdict=candidate_status,
        limit=limit,
        offset=offset,
    )


@router.get("/", response_model=PaginatedEvaluatedCandidatesResponse)
def get_all_applications(
    job_id: str | None = Query(default=None, description="Filter by job ID"),
    status: str | None = Query(default=None, description="Filter by evaluation status (SHORTLISTED, REJECTED, etc.)"),
    schedule: str | None = Query(default=None, description="Filter by schedule status (scheduled, unscheduled)"),
    min_score: int | None = Query(default=None, ge=0, le=100, description="Minimum ATS score filter"),
    max_score: int | None = Query(default=None, ge=0, le=100, description="Maximum ATS score filter"),
    date_from: str | None = Query(default=None, description="Filter by created date >= (ISO 8601)"),
    date_to: str | None = Query(default=None, description="Filter by created date <= (ISO 8601)"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of candidates to return"),
    offset: int = Query(default=0, ge=0, description="Number of candidates to skip"),
    final_verdict: str | None = Query(default=None, description='Set to "false" to exclude finalized candidates'),
    round_verdict: str | None = Query(default=None, description="Filter by round verdict (selected, rejected)"),
    ai: bool = Query(default=False, description="If true, omit cover_letter from response"),
    q: str | None = Query(default=None, description="Search candidates by name or email"),
    reject_reason: str | None = Query(default=None, description="Comma-separated rejection reasons (yoe,location,budget,notice_period)"),
    db: Session = Depends(get_db),
):
    service = ApplicationService(db)
    return service.get_applications_paginated(
        job_id=job_id,
        status_filter=status,
        schedule_filter=schedule,
        round_verdict=round_verdict,
        min_score=min_score,
        max_score=max_score,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
        exclude_finalized=final_verdict == "false",
        ai=ai,
        search=q,
        reject_reason=reject_reason,
    )


@router.get("/{application_id}", response_model=EvaluatedCandidate)
def get_application_by_id(
    application_id: str,
    ai: bool = Query(default=False, description="If true, omit cover_letter and include events"),
    db: Session = Depends(get_db),
):
    service = ApplicationService(db)
    result = service.get_application_by_id(application_id, ai=ai)
    if not result:
        raise HTTPException(status_code=404, detail="Application not found")
    return result


@router.patch("/{candidate_id}/final-verdict", response_model=EvaluationResponse)
def update_final_verdict(
    candidate_id: int,
    data: FinalVerdictUpdate,
    db: Session = Depends(get_db),
):
    service = ApplicationService(db)
    return service.set_final_verdict(candidate_id, data.verdict)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_application(data: ApplicationCreate):
    service = ApplicationService()
    return service.create_application(data)
