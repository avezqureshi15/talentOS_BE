from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.common.clients import AIClient, AIClientError, ResumeClient, SupabaseClient
from app.common.exceptions.base_exception import BaseAppException
from app.core.config import settings
from app.core.constants import EvaluationStatus
from app.core.logger import get_logger
from app.modules.applications.application_repository import ApplicationRepository
from app.modules.applications.application_schema import ApplicationCreate
from app.modules.evaluations.evaluation_schema import WebhookRecord

logger = get_logger(__name__)


class ApplicationService:
    def __init__(self, db: Session | None = None):
        self.db = db
        self.repo = ApplicationRepository(db) if db else None
        self.supabase = SupabaseClient()
        self.ai = AIClient()
        self.resume = ResumeClient()

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
    ) -> dict:
        if not self.repo:
            logger.warning("No DB session")
            return {"data": [], "total": 0, "limit": limit, "offset": offset}

        resolved_job_id = self.repo.resolve_supabase_job_id(job_id) if job_id else None
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
        )
        return {
            "data": [self.repo.to_candidate_dict(e) for e in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def evaluate_webhook(self, record: WebhookRecord) -> dict:
        app_dict = {
            "id": str(record.id),
            "job_id": str(record.job_id),
            "name": record.name,
            "email": record.email,
            "phone": record.phone,
            "cover_letter": record.cover_letter,
            "resume_url": record.resume_url,
            "current_ctc": record.current_ctc,
            "expected_ctc": record.expected_ctc,
            "location": record.location,
            "years_of_experience": record.years_of_experience,
            "notice_period": record.notice_period,
            "how_did_you_hear": record.how_did_you_hear,
            "linkedin_url": record.linkedin_url,
            "willing_to_relocate": record.willing_to_relocate,
        }
        result = self._evaluate_single(app_dict)
        return result or {"error": "Evaluation returned no result"}

    def _evaluate_single(self, app: dict) -> dict | None:
        application_id = str(app.get("id"))
        job_id = str(app.get("job_id"))

        if not self.repo:
            logger.warning("No DB session — skipping evaluation for application_id=%s", application_id)
            return None

        candidate = self.repo.get_candidate_by_application_id(application_id)

        if candidate and candidate.status in (
            EvaluationStatus.SHORTLISTED.value,
            EvaluationStatus.REJECTED.value,
            EvaluationStatus.INVALID.value,
            EvaluationStatus.FAILED.value,
        ):
            return self.repo.to_candidate_dict(candidate)

        if candidate is None:
            candidate = self.repo.create_queued_candidate(
                application_id=application_id,
                job_id=job_id,
                candidate_name=app.get("name"),
                candidate_email=app.get("email"),
                candidate_phone=app.get("phone"),
                cover_letter=app.get("cover_letter"),
                resume_url=app.get("resume_url"),
                current_ctc=app.get("current_ctc"),
                expected_ctc=app.get("expected_ctc"),
                location=app.get("location"),
                years_of_experience=app.get("years_of_experience"),
                notice_period=app.get("notice_period"),
                how_did_you_hear=app.get("how_did_you_hear"),
                linkedin_url=app.get("linkedin_url"),
                willing_to_relocate=app.get("willing_to_relocate", False),
            )

        resume_url = app.get("resume_url") or candidate.resume_url
        if not resume_url:
            candidate = self.repo.mark_result(
                candidate, EvaluationStatus.INVALID,
                error_reason="No resume_url provided",
            )
            return self.repo.to_candidate_dict(candidate)

        resume_text = self.resume.extract_text(resume_url)
        if len(resume_text.strip()) < settings.EVALUATION_MIN_RESUME_CHARS:
            candidate = self.repo.mark_result(
                candidate, EvaluationStatus.INVALID,
                error_reason="Resume is not text-extractable (image/scanned PDF)",
            )
            return self.repo.to_candidate_dict(candidate)

        candidate = self.repo.mark_processing(candidate)

        logger.debug("Raw extracted resume text for application_id=%s:\n%s", application_id, resume_text)

        candidate_meta_parts = []
        for label, val in [
            ("Years of Experience", candidate.years_of_experience),
            ("Current CTC", candidate.current_ctc),
            ("Expected CTC", candidate.expected_ctc),
            ("Location", candidate.location),
            ("Notice Period", candidate.notice_period),
        ]:
            if val:
                candidate_meta_parts.append(f"{label}: {val}")

        if candidate_meta_parts:
            resume_text += "\n\n--- Candidate Details ---\n" + "\n".join(candidate_meta_parts)
            logger.info(
                "Enriched resume with candidate details for application_id=%s", application_id
            )

        logger.debug("Final resume text sent to AI for application_id=%s:\n%s", application_id, resume_text)

        jd_details = self.supabase.fetch_jd_details(job_id)

        try:
            ai_result = self.ai.evaluate_resume(
                resume_txt=resume_text,
                jd_details=jd_details,
                custom_evaluation_criteria="",
            )
        except AIClientError as exc:
            logger.error("AI evaluation failed for application_id=%s: %s", application_id, str(exc))
            candidate = self.repo.mark_result(
                candidate, EvaluationStatus.FAILED,
                error_reason=str(exc),
            )
            return self.repo.to_candidate_dict(candidate)
        except Exception as exc:
            logger.exception("Unexpected error evaluating application_id=%s", application_id)
            candidate = self.repo.mark_result(
                candidate, EvaluationStatus.FAILED,
                error_reason=f"Unexpected error: {exc}",
            )
            return self.repo.to_candidate_dict(candidate)

        threshold = settings.ATS_THRESHOLD_DEFAULT
        is_shortlisted = ai_result.overall_score_percentage >= threshold
        status = EvaluationStatus.SHORTLISTED if is_shortlisted else EvaluationStatus.REJECTED

        candidate = self.repo.mark_result(
            candidate, status=status,
            fit_score=ai_result.overall_score_percentage,
            summary_md=ai_result.resume_summary,
            ats_threshold_used=threshold,
        )
        return self.repo.to_candidate_dict(candidate)

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
