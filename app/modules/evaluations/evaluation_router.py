from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.evaluations.evaluation_schema import (
    EvaluationResponse,
    IngestResponse,
    SupabaseWebhookPayload,
)
from app.modules.evaluations.evaluation_service import EvaluationService

# Ingest lives in the evaluations domain.
router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/evaluations", tags=["evaluations"])

# Candidate-read endpoints are exposed under the jobs path the HR/FE team consumes,
# while the logic stays in the evaluations module/service.
candidates_router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/jobs", tags=["evaluations"])


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_application(
    payload: SupabaseWebhookPayload,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    db: Session = Depends(get_db),
):
    """Supabase database webhook target — fired on INSERT into job_applications.

    Verifies the shared secret, deduplicates, persists a QUEUED evaluation,
    and publishes a task to Kafka. Returns 202 immediately.
    """
    service = EvaluationService(db)
    service.verify_webhook_secret(x_webhook_secret)
    return service.ingest(payload)


@router.post("/evaluate-sync", status_code=status.HTTP_200_OK)
def evaluate_sync(
    payload: SupabaseWebhookPayload,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    db: Session = Depends(get_db),
):
    """Synchronous webhook — receives Supabase INSERT, evaluates resume via AI,
    stores result in resume_evaluations, and returns the evaluation."""
    svc = EvaluationService(db)
    svc.verify_webhook_secret(x_webhook_secret)

    from app.modules.applications.application_service import ApplicationService
    app_svc = ApplicationService(db)
    result = app_svc.evaluate_webhook(payload.record)
    return result


@candidates_router.get("/{job_id}/candidates/shortlisted", response_model=list[EvaluationResponse])
def get_shortlisted_candidates(job_id: UUID, db: Session = Depends(get_db)):
    """HR view: candidates that scored at/above the ATS threshold for a job."""
    service = EvaluationService(db)
    return service.get_by_job(str(job_id), status="SHORTLISTED")


@candidates_router.get("/{job_id}/candidates", response_model=list[EvaluationResponse])
def get_all_candidates(job_id: UUID, db: Session = Depends(get_db)):
    """HR view: all evaluated candidates for a job (any status), ranked by score."""
    service = EvaluationService(db)
    return service.get_by_job(str(job_id))
