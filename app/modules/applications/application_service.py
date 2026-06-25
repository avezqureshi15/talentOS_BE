from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.common.exceptions.base_exception import BaseAppException
from app.core.config import settings
from app.core.constants import ErrorCode
from app.core.logger import get_logger
from app.modules.applications.application_schema import ApplicationCreate
from app.modules.evaluations.evaluation_model import EvaluationStatus
from app.modules.evaluations.evaluation_repository import EvaluationRepository
from app.modules.evaluations.evaluation_schema import (
    AIEvaluationRequest,
    AIEvaluationResponse,
    EvaluationMessage,
    WebhookRecord,
)
from app.modules.evaluations.evaluation_processor import TransientEvaluationError

logger = get_logger(__name__)

_APPLICATIONS_ENDPOINT: str = f"{settings.SUPABASE_FUNCTIONS_BASE_URL}/get-applications"
_JOBS_ENDPOINT: str = f"{settings.SUPABASE_FUNCTIONS_BASE_URL}/manage-job-listings"
_EMAIL_ENDPOINT: str = f"{settings.SUPABASE_FUNCTIONS_BASE_URL}/send-application-email"
_TIMEOUT: int = 30


class ApplicationService:
    def __init__(self, db: Session | None = None):
        self.db = db
        self.evaluation_repo = EvaluationRepository(db) if db else None

    def _parse_applications_response(self, raw: dict | list) -> list[dict]:
        if isinstance(raw, dict):
            return raw.get("data", raw.get("applications", []))
        if isinstance(raw, list):
            return raw
        return []

    def get_all_applications(self, job_id: str | None = None, status_filter: str | None = None) -> dict:
        if not self.evaluation_repo:
            logger.warning("No DB session")
            return {"data": []}

        if status_filter and job_id:
            status_upper = status_filter.upper().replace("-", "_")
            if status_upper == "NON_SHORTLISTED":
                filtered = self.evaluation_repo.get_by_job(job_id, status=EvaluationStatus.REJECTED.value)
            else:
                filtered = self.evaluation_repo.get_by_job(job_id, status=status_upper)
            return {"data": [self._to_candidate_dict(e) for e in filtered]}

        logger.info("Fetching applications from Supabase")
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.get(_APPLICATIONS_ENDPOINT)
                response.raise_for_status()
                raw = response.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.json()
            error_msg = body.get("error", "Unknown error")
            logger.error("Supabase error: status=%d | error=%s", exc.response.status_code, error_msg)
            raise BaseAppException(
                message=error_msg,
                code=ErrorCode.INTERNAL_ERROR,
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Supabase connection error: %s", str(exc))
            raise BaseAppException(
                message="Failed to connect to applications service",
                code=ErrorCode.INTERNAL_ERROR,
                status_code=502,
            ) from exc

        all_applications = self._parse_applications_response(raw)
        if job_id:
            all_applications = [a for a in all_applications if str(a.get("job_id", "")) == job_id]

        for app in all_applications:
            self._evaluate_single(app)

        result = [self._to_candidate_dict(e) for e in (self.evaluation_repo.get_by_job(job_id) if job_id else [])]
        return {"data": result}

    def evaluate_webhook(self, record: WebhookRecord) -> dict:
        app_dict = {
            "id": str(record.id),
            "job_id": str(record.job_id),
            "name": record.name,
            "email": record.email,
            "phone": record.phone,
            "cover_letter": record.cover_letter,
            "resume_url": record.resume_url,
        }
        result = self._evaluate_single(app_dict)
        return result or {"error": "Evaluation returned no result"}

    def _evaluate_single(self, app: dict) -> dict | None:
        application_id = str(app.get("id"))
        job_id = str(app.get("job_id"))

        if not self.evaluation_repo:
            logger.warning("No DB session — skipping evaluation for application_id=%s", application_id)
            return None

        evaluation = self.evaluation_repo.get_by_application_id(application_id)

        if evaluation and evaluation.status in (
            EvaluationStatus.SHORTLISTED.value,
            EvaluationStatus.REJECTED.value,
            EvaluationStatus.INVALID.value,
            EvaluationStatus.FAILED.value,
        ):
            return self._to_candidate_dict(evaluation)

        if evaluation is None:
            evaluation = self.evaluation_repo.create_queued(
                application_id=application_id,
                job_id=job_id,
                candidate_name=app.get("name"),
                candidate_email=app.get("email"),
                candidate_phone=app.get("phone"),
                cover_letter=app.get("cover_letter"),
                resume_url=app.get("resume_url"),
            )

        resume_url = app.get("resume_url") or evaluation.resume_url
        if not resume_url:
            self.evaluation_repo.mark_result(
                evaluation, EvaluationStatus.INVALID,
                error_reason="No resume_url provided",
            )
            evaluation = self.evaluation_repo.get_by_application_id(application_id)
            return self._to_candidate_dict(evaluation)

        resume_text = self._extract_resume_text(resume_url)
        if len(resume_text.strip()) < settings.EVALUATION_MIN_RESUME_CHARS:
            self.evaluation_repo.mark_result(
                evaluation, EvaluationStatus.INVALID,
                error_reason="Resume is not text-extractable (image/scanned PDF)",
            )
            evaluation = self.evaluation_repo.get_by_application_id(application_id)
            return self._to_candidate_dict(evaluation)

        self.evaluation_repo.mark_processing(evaluation)

        jd_details = self._fetch_jd_details(job_id)

        try:
            ai_result = self._call_ai_service(
                resume_txt=resume_text,
                jd_details=jd_details,
                custom_evaluation_criteria="",
            )
        except TransientEvaluationError as exc:
            logger.error("AI evaluation failed for application_id=%s: %s", application_id, str(exc))
            self.evaluation_repo.mark_result(
                evaluation, EvaluationStatus.FAILED,
                error_reason=str(exc),
            )
            evaluation = self.evaluation_repo.get_by_application_id(application_id)
            return self._to_candidate_dict(evaluation)
        except Exception as exc:
            logger.exception("Unexpected error evaluating application_id=%s", application_id)
            self.evaluation_repo.mark_result(
                evaluation, EvaluationStatus.FAILED,
                error_reason=f"Unexpected error: {exc}",
            )
            evaluation = self.evaluation_repo.get_by_application_id(application_id)
            return self._to_candidate_dict(evaluation)

        threshold = settings.ATS_THRESHOLD_DEFAULT
        is_shortlisted = ai_result.overall_score_percentage >= threshold
        status = EvaluationStatus.SHORTLISTED if is_shortlisted else EvaluationStatus.REJECTED

        self.evaluation_repo.mark_result(
            evaluation, status=status,
            fit_score=ai_result.overall_score_percentage,
            summary_md=ai_result.resume_summary,
            ats_threshold_used=threshold,
        )

        evaluation = self.evaluation_repo.get_by_application_id(application_id)
        return self._to_candidate_dict(evaluation)

    def _to_candidate_dict(self, evaluation) -> dict:
        return {
            "id": evaluation.application_id,
            "job_id": evaluation.job_id,
            "name": evaluation.candidate_name,
            "email": evaluation.candidate_email,
            "phone": evaluation.candidate_phone,
            "cover_letter": evaluation.cover_letter,
            "resume_url": evaluation.resume_url,
            "status": evaluation.status,
            "fit_score": evaluation.fit_score,
            "summary_md": evaluation.summary_md,
            "evaluated_at": evaluation.evaluated_at.isoformat() if evaluation.evaluated_at else None,
        }

    def _extract_resume_text(self, resume_url: str) -> str:
        from io import BytesIO
        from pypdf import PdfReader

        headers = {}
        if settings.SUPABASE_SERVICE_ROLE_KEY:
            headers["Authorization"] = f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"
        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(resume_url, headers=headers)
                response.raise_for_status()
                content = response.content
        except httpx.HTTPError as exc:
            raise TransientEvaluationError(f"Resume download failed: {exc}") from exc

        try:
            reader = PdfReader(BytesIO(content))
            return "".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            logger.warning("PDF parse error: %s", str(exc))
            return ""

    def _fetch_jd_details(self, job_id: str) -> str:
        endpoint = f"{settings.SUPABASE_FUNCTIONS_BASE_URL}/manage-job-listings"
        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(endpoint, params={"id": job_id})
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise TransientEvaluationError(f"JD fetch failed: {exc}") from exc

        data = body.get("data", body) if isinstance(body, dict) else {}
        title = data.get("title", "")
        description = data.get("description", "")
        requirements = data.get("requirements") or []
        req_text = "\n".join(f"- {r}" for r in requirements) if isinstance(requirements, list) else str(requirements)
        return f"Title: {title}\n\nDescription:\n{description}\n\nRequirements:\n{req_text}".strip()

    def _call_ai_service(self, resume_txt: str, jd_details: str, custom_evaluation_criteria: str) -> AIEvaluationResponse:
        if not settings.AI_SERVICE_BASE_URL:
            raise TransientEvaluationError("AI_SERVICE_BASE_URL not configured")

        url = f"{settings.AI_SERVICE_BASE_URL.rstrip('/')}/api/v1/evaluation/evaluate-resume"
        request = AIEvaluationRequest(
            resume_txt=resume_txt,
            custom_evaluation_criteria=custom_evaluation_criteria,
            jd_details=jd_details,
        )
        try:
            with httpx.Client(timeout=settings.AI_SERVICE_TIMEOUT) as client:
                response = client.post(url, json=request.model_dump())
                response.raise_for_status()
                return AIEvaluationResponse.model_validate(response.json())
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                raise TransientEvaluationError(f"AI service 5xx: {exc}") from exc
            raise TransientEvaluationError(f"AI service error {exc.response.status_code}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise TransientEvaluationError(f"AI service unreachable: {exc}") from exc

    def _fetch_job_title(self, job_id: UUID) -> str:
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.get(_JOBS_ENDPOINT, params={"id": str(job_id)})
                response.raise_for_status()
                body = response.json()
                return body.get("data", {}).get("title", "Job Listing")
        except Exception as exc:
            logger.warning("Could not fetch job title for job_id=%s: %s", job_id, str(exc))
            return "Job Listing"

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

        job_title = self._fetch_job_title(data.job_id)

        payload = self._to_camel_case(data.model_dump())
        payload["jobTitle"] = job_title

        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.post(_EMAIL_ENDPOINT, json=payload)
                response.raise_for_status()
                email_result = response.json()
                logger.info("Application email sent: id=%s", email_result.get("id"))
                return {
                    "message": "Application submitted successfully",
                    "email_id": email_result.get("id"),
                }
        except httpx.HTTPStatusError as exc:
            body = exc.response.json()
            logger.error("Failed to send email: status=%d | error=%s", exc.response.status_code, body.get("error"))
            raise BaseAppException(
                message="Failed to send application email",
                code=ErrorCode.EMAIL_SEND_FAILED,
                status_code=502,
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Email service unavailable: %s", str(exc))
            raise BaseAppException(
                message="Email service unavailable",
                code=ErrorCode.EMAIL_SEND_FAILED,
                status_code=502,
            ) from exc
