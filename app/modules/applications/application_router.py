from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.modules.applications.application_schema import (
    ApplicationCreate,
    EvaluatedCandidate,
    FinalVerdictUpdate,
    PaginatedEvaluatedCandidatesResponse,
    RoundStatusUpdate,
)
from app.modules.applications.application_service import ApplicationService
from app.modules.evaluations.evaluation_schema import EvaluationResponse

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/applications", tags=["applications"], dependencies=[Depends(require_permission(Permission.APPLICATION_VIEW))])


@router.get("/final-verdicts", response_model=PaginatedEvaluatedCandidatesResponse)
def get_finalized_candidates(
    job_id: str | None = Query(default=None, description="Filter by job ID"),
    candidate_status: str | None = Query(default=None, description="Filter by final verdict (selected, rejected)"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    service = ApplicationService(db)
    return service.get_finalized_candidates_paginated(
        verdict=candidate_status,
        job_id=job_id,
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
    stage: str | None = Query(default=None, description="Filter by pipeline stage (resume-shortlisting, screening, interview, waiting-evaluation, evaluated)"),
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
        stage=stage,
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


@router.patch("/{candidate_id}/round-status", dependencies=[Depends(require_permission(Permission.APPLICATION_WORKFLOW))])
def update_candidate_round_status(
    candidate_id: int,
    data: RoundStatusUpdate,
    db: Session = Depends(get_db),
):
    service = ApplicationService(db)
    return service.set_candidate_round_status(candidate_id, data)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_application(data: ApplicationCreate):
    service = ApplicationService()
    return service.create_application(data)


@router.post("/candidates/{candidate_id}/move-to-next-round", response_model=EvaluationResponse, dependencies=[Depends(require_permission(Permission.APPLICATION_WORKFLOW))])
def move_candidate_to_next_round(candidate_id: int, db: Session = Depends(get_db)):
    service = ApplicationService(db)
    return service.move_to_next_round(candidate_id)
