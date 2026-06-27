"""Resume evaluation processing logic, invoked by the Kafka worker.

For one queued application this:
  1. loads the evaluation row and marks it PROCESSING,
  2. downloads the resume PDF from Supabase Storage,
  3. extracts text (pypdf) and validates it is a text-based PDF,
  4. fetches the job description from Supabase,
  5. calls the talentOS_AI /evaluate-resume endpoint,
  6. applies the ATS threshold and stores the outcome.

Raises TransientEvaluationError for retryable failures (network/5xx) so the
worker can retry / route to the DLQ. All terminal outcomes are written to the
candidates table.
"""
from io import BytesIO

import httpx
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import EvaluationStatus
from app.modules.evaluations.evaluation_repository import EvaluationRepository
from app.modules.evaluations.evaluation_schema import (
    AIEvaluationRequest,
    AIEvaluationResponse,
    EvaluationMessage,
)

logger = get_logger(__name__)


class TransientEvaluationError(Exception):
    """Retryable failure (network error, AI 5xx, timeout)."""


class EvaluationProcessor:
    def __init__(self, db: Session):
        self.db = db
        self.repository = EvaluationRepository(db)

    def process(self, message: EvaluationMessage) -> None:
        evaluation = self.repository.get_by_application_id(message.application_id)
        if evaluation is None:
            logger.warning(
                "No evaluation row for application_id=%s — skipping", message.application_id
            )
            return

        if evaluation.status in (
            EvaluationStatus.SHORTLISTED.value,
            EvaluationStatus.REJECTED.value,
            EvaluationStatus.INVALID.value,
        ):
            logger.info(
                "Application already in terminal state (%s) — skipping idempotently: %s",
                evaluation.status,
                message.application_id,
            )
            return

        self.repository.mark_processing(evaluation)
        logger.info("Processing application_id=%s | job_id=%s", message.application_id, message.job_id)

        if not message.resume_url:
            self.repository.mark_result(
                evaluation, EvaluationStatus.INVALID, error_reason="No resume_url provided"
            )
            return
       
        resume_text = self._extract_resume_text(message.resume_url)
        if len(resume_text.strip()) < settings.EVALUATION_MIN_RESUME_CHARS:
            logger.info("Non-text/empty PDF for application_id=%s — marking INVALID", message.application_id)
            self.repository.mark_result(
                evaluation,
                EvaluationStatus.INVALID,
                error_reason="Resume is not text-extractable (image/scanned PDF)",
            )
            return

        jd_details = self._fetch_jd_details(message.job_id)
        ai_result = self._call_ai_service(
            resume_txt=resume_text,
            jd_details=jd_details,
            custom_evaluation_criteria="",  # TODO: source per-job HR criteria when available
        )

        threshold = settings.ATS_THRESHOLD_DEFAULT
        is_shortlisted = ai_result.overall_score_percentage >= threshold
        status = EvaluationStatus.SHORTLISTED if is_shortlisted else EvaluationStatus.REJECTED

        self.repository.mark_result(
            evaluation,
            status=status,
            fit_score=ai_result.overall_score_percentage,
            summary_md=ai_result.resume_summary,
            ats_threshold_used=threshold,
        )
        logger.info(
            "Evaluated application_id=%s | score=%d | threshold=%d | status=%s",
            message.application_id,
            ai_result.overall_score_percentage,
            threshold,
            status.value,
        )

    def _extract_resume_text(self, resume_url: str) -> str:
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
        except Exception as exc:  # noqa: BLE001 — corrupt PDF is terminal, not retryable
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

    def _call_ai_service(
        self, resume_txt: str, jd_details: str, custom_evaluation_criteria: str
    ) -> AIEvaluationResponse:
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
            # 5xx is retryable; 4xx is a contract problem (still retry-limited by worker).
            if exc.response.status_code >= 500:
                raise TransientEvaluationError(f"AI service 5xx: {exc}") from exc
            raise TransientEvaluationError(f"AI service error {exc.response.status_code}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise TransientEvaluationError(f"AI service unreachable: {exc}") from exc
