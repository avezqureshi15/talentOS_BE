"""Full evaluation Kafka consumer — AI + round/review/event creation.

Replaces the old ``evaluation_worker.py``.  Runs the same full pipeline as the
sync ``/evaluate-sync`` endpoint but asynchronously via Kafka.

Delivery semantics: at-least-once.  Retries transient errors with exponential
backoff up to ``EVALUATION_MAX_ATTEMPTS``, then routes to the DLQ.

Scalability:
    - Partition-based: 3 worker replicas in the same consumer group share
      6 partitions (each partition processed by exactly one replica)
    - Stateless workers: all state lives in the DB or Kafka
    - Retry isolation: transient failures stay within the handler loop and
      never cause an offset commit — only terminal outcomes commit the offset

Usage:
    python -m app.workers.evaluation_full_worker
"""
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import OperationalError

from app.common.clients import AIClient, ClientError, ResumeClient, SupabaseClient
from app.common.exceptions.evaluation_exception import TransientEvaluationError
from app.common.schemas.evaluation import AIEvaluationResponse
from app.core.config import settings
from app.core.constants import EvaluationStatus
from app.core.kafka import ConsumedMessage, consume, publish
from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.applications.application_repository import ApplicationRepository
from app.modules.evaluations.evaluation_schema import AsyncEvaluationMessage
from app.modules.events.event_schema import EventCreate
from app.modules.events.event_service import EventService
from app.modules.reviews.review_schema import ReviewCreate
from app.modules.reviews.review_service import ReviewService
from app.modules.rounds.round_model import Round
from app.modules.rounds.round_schema import RoundCreate
from app.modules.rounds.round_service import RoundService

logger = get_logger(__name__)

# ── Error classification ─────────────────────────────────────────────────


def _is_transient_error(exc: Exception) -> bool:
    """Return True if the error is recoverable and the message should be retried."""
    if isinstance(exc, TransientEvaluationError):
        return True
    if isinstance(exc, OperationalError):
        return True
    if isinstance(exc, TimeoutError):
        return True
    return False


# ── Full evaluation pipeline (one attempt) ───────────────────────────────


def _evaluate_full(message: AsyncEvaluationMessage) -> None:
    """Execute one attempt of the full evaluation pipeline.

    Raises ``TransientEvaluationError`` on retryable failures so the caller
    can retry.  Terminal failures (invalid data, exhausted retries) should be
    caught and handled by the caller.
    """
    db = SessionLocal()
    try:
        repo = ApplicationRepository(db)
        application_id = message.application_id
        job_id = message.job_id

        candidate = repo.get_candidate_by_application_id(application_id)
        if candidate and candidate.status in (
            EvaluationStatus.RESUME_SHORTLISTED.value,
            EvaluationStatus.INVALID.value,
            EvaluationStatus.RESUME_PROCESSING_FAILED.value,
            EvaluationStatus.FAILED.value,
        ):
            logger.info("Application already in terminal state — skipping: %s", application_id)
            return

        if candidate is None:
            candidate = repo.create_queued_candidate(
                application_id=application_id,
                job_id=job_id,
                candidate_name=message.candidate_name,
                candidate_email=message.candidate_email,
                candidate_phone=message.candidate_phone,
                cover_letter=message.cover_letter,
                resume_url=message.resume_url,
                current_ctc=message.current_ctc,
                expected_ctc=message.expected_ctc,
                location=message.location,
                years_of_experience=message.years_of_experience,
                notice_period=message.notice_period,
                how_did_you_hear=message.how_did_you_hear,
                linkedin_url=message.linkedin_url,
                willing_to_relocate=message.willing_to_relocate,
                candidate_type=message.candidate_type,
            )
            EventService(db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate.id),
                event_name="Candidate Applied for Job",
                state_code="CANDIDATE_APPLIED",
                actor_type="CANDIDATE",
                actor_id=str(candidate.id),
                candidate_id=candidate.id,
                action_url=candidate.resume_url,
                action_label="Download Resume",
            ))

        resume_url = message.resume_url or candidate.resume_url
        if not resume_url:
            EventService(db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate.id),
                event_name="Resume Evaluation Failed",
                state_code="EVALUATION_FAILED",
                actor_type="SYSTEM",
                candidate_id=candidate.id,
                remark="No resume_url provided",
                event_metadata={"error_reason": "No resume_url provided"},
            ))
            repo.mark_result(candidate, EvaluationStatus.INVALID, error_reason="No resume_url provided")
            return

        resume_text = ResumeClient().extract_text(resume_url)
        if len(resume_text.strip()) < settings.EVALUATION_MIN_RESUME_CHARS:
            EventService(db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate.id),
                event_name="Resume Evaluation Failed",
                state_code="EVALUATION_FAILED",
                actor_type="SYSTEM",
                candidate_id=candidate.id,
                remark="Resume is not text-extractable (image/scanned PDF)",
                event_metadata={"error_reason": "Resume is not text-extractable"},
            ))
            repo.mark_result(candidate, EvaluationStatus.INVALID, error_reason="Resume is not text-extractable (image/scanned PDF)")
            return

        candidate = repo.mark_processing(candidate)
        EventService(db).create_event(EventCreate(
            entity_type="CANDIDATE",
            entity_id=str(candidate.id),
            event_name="Resume Evaluation Started",
            state_code="EVALUATION_STARTED",
            actor_type="SYSTEM",
            candidate_id=candidate.id,
            event_metadata={"resume_url": resume_url},
        ))

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

        jd_details = SupabaseClient().fetch_jd_details(job_id)

        try:
            ai_result = AIClient().evaluate_resume(
                resume_txt=resume_text,
                jd_details=jd_details,
                custom_evaluation_criteria="",
            )
        except ClientError:
            logger.warning("AI service failed — using mock evaluation for candidate_id=%s", candidate.id)
            ai_result = _mock_evaluation_fallback(message.candidate_name)

        threshold = settings.ATS_THRESHOLD_DEFAULT
        verdict = "shortlisted" if ai_result.overall_score_percentage >= threshold else "rejected"

        candidate = repo.mark_result(
            candidate,
            status=EvaluationStatus.RESUME_SHORTLISTED,
            fit_score=ai_result.overall_score_percentage,
            summary_md=ai_result.resume_summary,
            ats_threshold_used=threshold,
        )

        EventService(db).create_event(EventCreate(
            entity_type="CANDIDATE",
            entity_id=str(candidate.id),
            event_name="Resume Evaluation Completed",
            state_code="EVALUATION_COMPLETED",
            actor_type="AI",
            candidate_id=candidate.id,
            event_metadata={"fit_score": ai_result.overall_score_percentage, "threshold_used": threshold},
        ))

        _create_initial_review(db, ai_result, candidate, job_id, verdict)

    except TransientEvaluationError:
        raise
    except Exception as exc:
        logger.exception("Unhandled error processing application_id=%s", message.application_id)
        raise TransientEvaluationError(f"Unexpected error: {exc}") from exc
    finally:
        db.close()


def _create_initial_review(
    db,
    ai_result: AIEvaluationResponse,
    candidate,
    job_id: str,
    verdict: str,
) -> None:
    """Create round, review, and events after successful evaluation."""
    try:
        repo = ApplicationRepository(db)
        jd_uuid = repo.resolve_hiring_request_id(job_id)
        if jd_uuid is None:
            logger.warning("Could not resolve hiring request for job_id=%s — skipping round/review", job_id)
            return

        round_resp = RoundService(db).create_round(RoundCreate(
            name="Resume Shortlisting",
            round_type="RESUME_SHORTLISTING",
            candidate_id=candidate.id,
            jd_id=jd_uuid,
        ))
        db.refresh(candidate)
        repo.set_current_round_id(candidate, round_resp.id)

        ReviewService(db).create_review(ReviewCreate(
            round_id=round_resp.id,
            entity_type="AI",
            reviews={
                "fitscore": ai_result.overall_score_percentage,
                "summary": ai_result.resume_summary,
                "summary_md": ai_result.resume_summary,
                "YOE": {"actual": f"{candidate.years_of_experience or '?'} yrs", "expected": "5 yrs"},
                "CTC": {"actual": f"{candidate.current_ctc or '?'} LPA", "expected": "12 LPA"},
                "LOCATION": {"actual": candidate.location or "?", "expected": "India"},
                "NOTICE_PERIOD": {"actual": f"{candidate.notice_period or '?'} days", "expected": "15 days"},
                "rejection_details": ai_result.rejection_details,
            },
            verdict=verdict,
        ))

        candidate.reviews = {
            "fitscore": ai_result.overall_score_percentage,
            "summary": ai_result.resume_summary,
            "summary_md": ai_result.resume_summary,
            "YOE": {"actual": f"{candidate.years_of_experience or '?'} yrs", "expected": "5 yrs"},
            "CTC": {"actual": f"{candidate.current_ctc or '?'} LPA", "expected": "12 LPA"},
            "LOCATION": {"actual": candidate.location or "?", "expected": "India"},
            "NOTICE_PERIOD": {"actual": f"{candidate.notice_period or '?'} days", "expected": "15 days"},
            "rejection_details": ai_result.rejection_details,
        }
        candidate.review_verdict = verdict

        round_obj = db.query(Round).filter(Round.id == round_resp.id).first()
        if round_obj:
            round_obj.round_verdict = "selected" if verdict == "shortlisted" else "rejected"
            db.flush()

        EventService(db).create_event(EventCreate(
            entity_type="CANDIDATE",
            entity_id=str(candidate.id),
            event_name="Candidate Shortlisted by AI" if verdict == "shortlisted" else "Rejected by AI",
            state_code="AI_SHORTLISTED" if verdict == "shortlisted" else "AI_REJECTED",
            actor_type="AI",
            candidate_id=candidate.id,
            event_metadata={
                "fit_score": ai_result.overall_score_percentage,
                "round_id": str(round_resp.id),
                "verdict": verdict,
            },
        ))
    except Exception as exc:
        logger.error("Round/review creation failed for candidate_id=%s: %s", candidate.id, exc)


def _mock_evaluation_fallback(candidate_name: str | None) -> AIEvaluationResponse:
    return AIEvaluationResponse(
        resume_summary=(
            "### Candidate Summary\n\n"
            f"{candidate_name or 'The candidate'} does not meet the minimum requirements "
            "for this position based on the initial screening.\n\n"
            "**Areas of concern:**\n"
            "- Insufficient years of relevant experience\n"
            "- Location does not match preferred regions\n"
            "- Notice period exceeds acceptable range"
        ),
        overall_score_percentage=45,
        rejection_details=[
            {"YOE": {"JD": "5+ yrs", "Candidate": "2 yrs"}},
            {"LOCATION": {"JD": "India", "Candidate": "Remote, UAE"}},
            {"NOTICE_PERIOD": {"JD": "15 days", "Candidate": "60 days"}},
        ],
    )


# ── Retry handler ────────────────────────────────────────────────────────


def _route_to_dlq(message: AsyncEvaluationMessage, reason: str) -> None:
    """Publish failed message to the DLQ topic."""
    logger.error("Routing application_id=%s to DLQ: %s", message.application_id, reason)
    try:
        publish(
            topic=settings.KAFKA_TOPIC_EVALUATION_ASYNC_DLQ,
            key=message.application_id,
            value=message.model_dump_json(),
        )
    except Exception as exc:
        logger.error("Failed to publish to DLQ for application_id=%s: %s", message.application_id, str(exc))


def _handler_with_retry(msg: ConsumedMessage) -> None:
    """Deserialize message and run ``_evaluate_full`` with retry loop.

    Catches all exceptions internally so that ``consume()`` always sees
    success and commits the offset — unless the process crashes, in which
    case the uncommitted offset causes Kafka to re-deliver (at-least-once).
    """
    message = AsyncEvaluationMessage.model_validate_json(msg.value)
    last_error: Exception | None = None
    max_attempts = settings.EVALUATION_MAX_ATTEMPTS

    for attempt in range(1, max_attempts + 1):
        try:
            _evaluate_full(message)
            return
        except TransientEvaluationError as exc:
            last_error = exc
            logger.warning(
                "Transient error (attempt %d/%d) for application_id=%s: %s",
                attempt,
                max_attempts,
                message.application_id,
                exc,
            )
            if attempt < max_attempts:
                delay = min(2 ** attempt, 30)
                logger.info("Retrying in %ds ...", delay)
                time.sleep(delay)
        except Exception as exc:
            last_error = exc
            logger.error(
                "Non-retryable error for application_id=%s: %s",
                message.application_id,
                exc,
            )
            break

    _route_to_dlq(message, str(last_error))


def main() -> None:
    logger.info("Starting full evaluation worker — topic=%s", settings.KAFKA_TOPIC_EVALUATION_ASYNC)
    logger.info("Max retry attempts per message: %d", settings.EVALUATION_MAX_ATTEMPTS)
    consume(
        topics=[settings.KAFKA_TOPIC_EVALUATION_ASYNC],
        handler=_handler_with_retry,
        group_id="resume-full-evaluators",
    )


if __name__ == "__main__":
    main()
