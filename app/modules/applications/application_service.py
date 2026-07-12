from uuid import UUID

from sqlalchemy.orm import Session

from app.common.clients import SupabaseClient
from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import EvaluationStatus
from app.core.logger import get_logger
from app.modules.applications.application_evaluation_service import ApplicationEvaluationService
from app.modules.applications.application_repository import ApplicationRepository
from app.modules.applications.application_schema import ApplicationCreate
from app.modules.applications.application_state_service import ApplicationStateService
from app.modules.evaluations.evaluation_schema import EvaluationResponse, WebhookRecord

logger = get_logger(__name__)


class ApplicationService:
    def __init__(self, db: Session | None = None):
        self.db = db
        self.repo = ApplicationRepository(db) if db else None
        self.eval_svc = ApplicationEvaluationService(db, self.repo) if db else None
        self.state_svc = ApplicationStateService(db, self.repo) if db else None
        self.supabase = SupabaseClient()
    def get_application_by_id(self, application_id: str) -> dict | None:
        if not self.repo:
            logger.warning("No DB session")
            return None
        candidate = self.repo.get_candidate_by_application_id(application_id)
        if not candidate:
            return None
        return self.repo.to_candidate_dict(candidate)
    def get_applications_paginated(
        self,
        job_id: str | None = None,
        status_filter: str | None = None,
        schedule_filter: str | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 20,
        offset: int = 0,
        exclude_finalized: bool = False,
    ) -> dict:
        if not self.repo:
            logger.warning("No DB session")
            return {"data": [], "total": 0, "limit": limit, "offset": offset}

        resolved_job_id = self.repo.resolve_external_job_id(job_id) if job_id else None
        if job_id and not resolved_job_id:
            return {"data": [], "total": 0, "limit": limit, "offset": offset}

        status_upper = None
        parsed_schedule = None
        if status_filter:
            status_upper = status_filter.upper().replace("-", "_")
            if status_upper == "NON_SHORTLISTED":
                status_upper = EvaluationStatus.REJECTED.value
            elif status_upper == "SCHEDULED":
                parsed_schedule = "scheduled"
                status_upper = None
            elif status_upper == "UNSCHEDULED":
                parsed_schedule = "unscheduled"
                status_upper = None
        if schedule_filter and not parsed_schedule:
            parsed_schedule = schedule_filter.lower()

        items, total = self.repo.get_candidates_by_job_paginated(
            job_id=resolved_job_id,
            status=status_upper,
            schedule=parsed_schedule,
            min_score=min_score,
            max_score=max_score,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
            exclude_finalized=exclude_finalized,
        )
        return {
            "data": [self.repo.to_candidate_dict(e) for e in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    def get_finalized_candidates_paginated(
        self,
        verdict: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        if not self.repo:
            return {"data": [], "total": 0, "limit": limit, "offset": offset}
        items, total = self.repo.get_finalized_candidates(
            verdict=verdict.upper() if verdict else None,
            limit=limit,
            offset=offset,
        )
        return {
            "data": [self.repo.to_candidate_dict(e) for e in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    def evaluate_webhook(self, record: WebhookRecord) -> dict:
        if not self.eval_svc:
            return {"error": "Evaluation service not available"}
        return self.eval_svc.evaluate_webhook(record)

    def _to_camel_case(self, snake_data: dict) -> dict:
        mapping = {
            "job_id": "jobTitle",
            "cover_letter": "coverLetter",
            "resume_url": "resumeUrl",
        }
        camel = {}
        for key, value in snake_data.items():
            mapped = mapping.get(key, key)
            camel[mapped] = value
        return camel

    def trigger_transition(self, trigger: str, *, candidate_id: int | None = None, round_id: UUID | None = None) -> EvaluationResponse:
        if not self.state_svc: raise ValueError("State service not available")
        return self.state_svc.trigger_transition(trigger, candidate_id=candidate_id, round_id=round_id)

    def handle_hr_verdict(self, round_id: UUID, verdict: str | None) -> None:
        if self.state_svc: self.state_svc.handle_hr_verdict(round_id, verdict)

    def set_final_verdict(self, candidate_id: int, verdict: str) -> EvaluationResponse:
        if not self.state_svc: raise ValueError("State service not available")
        return self.state_svc.set_final_verdict(candidate_id, verdict)

    def update_candidate_status(self, candidate_id: int, new_status: str) -> EvaluationResponse:
        if not self.state_svc: raise ValueError("State service not available")
        return self.state_svc.update_candidate_status(candidate_id, new_status)
    def create_application(self, data: ApplicationCreate) -> dict:
        logger.info("Creating application: job_id=%s | name=%s", data.job_id, data.name)
        job_title = self.supabase.fetch_job_title(data.job_id)
        payload = self._to_camel_case(data.model_dump())
        payload["jobTitle"] = job_title
        try:
            email_result = self.supabase.send_application_email(payload)
            logger.info("Application email sent: id=%s", email_result.get("id"))
            return {
                "message": "Application submitted successfully",
                "email_id": email_result.get("id"),
            }
        except BaseAppException:
            raise
