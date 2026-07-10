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
from sqlalchemy.orm import Session

from app.common.clients import AIClient, AIClientError, ResumeClient, SupabaseClient
from app.core.config import settings
from app.core.constants import EvaluationStatus
from app.core.logger import get_logger
from app.modules.evaluations.evaluation_repository import EvaluationRepository
from app.modules.evaluations.evaluation_schema import EvaluationMessage

logger = get_logger(__name__)


class TransientEvaluationError(Exception):
    """Retryable failure (network error, AI 5xx, timeout)."""


class EvaluationProcessor:
    def __init__(self, db: Session):
        self.db = db
        self.repository = EvaluationRepository(db)
        self.supabase = SupabaseClient()
        self.ai = AIClient()
        self.resume = ResumeClient()

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

        resume_text = self.resume.extract_text(message.resume_url)
        if len(resume_text.strip()) < settings.EVALUATION_MIN_RESUME_CHARS:
            logger.info("Non-text/empty PDF for application_id=%s — marking INVALID", message.application_id)
            self.repository.mark_result(
                evaluation,
                EvaluationStatus.INVALID,
                error_reason="Resume is not text-extractable (image/scanned PDF)",
            )
            return

        logger.debug("Raw extracted resume text for application_id=%s:\n%s", message.application_id, resume_text)

        candidate_meta_parts = []
        for label, val in [
            ("Years of Experience", evaluation.years_of_experience),
            ("Current CTC", evaluation.current_ctc),
            ("Expected CTC", evaluation.expected_ctc),
            ("Location", evaluation.location),
            ("Notice Period", evaluation.notice_period),
        ]:
            if val:
                candidate_meta_parts.append(f"{label}: {val}")

        if candidate_meta_parts:
            resume_text += "\n\n--- Candidate Details ---\n" + "\n".join(candidate_meta_parts)
            logger.info(
                "Enriched resume with candidate details for application_id=%s", message.application_id
            )

        logger.debug("Final resume text sent to AI for application_id=%s:\n%s", message.application_id, resume_text)

        try:
            jd_details = self.supabase.fetch_jd_details(message.job_id)
        except Exception as exc:
            raise TransientEvaluationError(f"JD fetch failed: {exc}") from exc

        try:
            ai_result = self.ai.evaluate_resume(
                resume_txt=resume_text,
                jd_details=jd_details,
                custom_evaluation_criteria="",
            )
        except AIClientError as exc:
            raise TransientEvaluationError(str(exc)) from exc
        except Exception as exc:
            raise TransientEvaluationError(f"AI evaluation failed: {exc}") from exc

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
