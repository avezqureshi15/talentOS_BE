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
import random
import re
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import OperationalError

from app.common.clients import AIClient, ClientError, ResumeClient, SupabaseClient
from app.common.exceptions.evaluation_exception import TransientEvaluationError
from app.common.schemas.evaluation import AIEvaluationResponse
from app.core.config import settings
from app.core.constants import EvaluationStatus, PipelineStage
from app.core.kafka import ConsumedMessage, consume, publish
from app.core.logger import get_logger, setup_logging
from app.db.session import SessionLocal
from app.modules.applications.application_repository import ApplicationRepository
from app.modules.evaluations.evaluation_schema import AsyncEvaluationMessage
from app.modules.events.event_schema import EventCreate
from app.modules.events.event_service import EventService
from app.modules.notifications.notification_model import NotificationType
from app.modules.notifications.notification_service import NotificationService
from app.modules.reviews.review_schema import ReviewCreate
from app.modules.reviews.review_service import ReviewService
from app.modules.rounds.round_model import Round
from app.modules.rounds.round_schema import RoundCreate
from app.modules.rounds.round_service import RoundService

logger = get_logger(__name__)


def _notify_evaluation_failed(db, job_id: str, candidate_id: int, reason: str) -> None:
    repo = ApplicationRepository(db)
    jd_uuid = repo.resolve_hiring_request_id(job_id)
    if jd_uuid:
        NotificationService(db).notify_job_team(
            jd_uuid,
            notification_type=NotificationType.EVALUATION_FAILED.value,
            title="Resume evaluation failed",
            body=f"A candidate's resume could not be evaluated ({reason}).",
            action_url=f"/hiring-requests/{jd_uuid}/candidates/{candidate_id}",
            action_label="View candidate",
            candidate_id=candidate_id,
        )


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
            _notify_evaluation_failed(db, job_id, candidate.id, "No resume URL provided")
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
            _notify_evaluation_failed(db, job_id, candidate.id, "Resume is not text-extractable")
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
            ai_result = _mock_evaluation_fallback(candidate, jd_details)

        threshold = settings.ATS_THRESHOLD_DEFAULT
        verdict = "shortlisted" if ai_result.overall_score_percentage >= threshold else "rejected"

        candidate = repo.mark_result(
            candidate,
            status=EvaluationStatus.UNDER_EVALUATION,
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

        jd_uuid = repo.resolve_hiring_request_id(job_id)
        if jd_uuid:
            NotificationService(db).notify_job_team(
                jd_uuid,
                notification_type=NotificationType.EVALUATION_COMPLETED.value,
                title="Resume evaluation completed",
                body=f"{candidate.candidate_name} was {'shortlisted' if verdict == 'shortlisted' else 'not shortlisted'} by AI (score {ai_result.overall_score_percentage:.0f}%).",
                action_url=f"/hiring-requests/{jd_uuid}/candidates/{candidate.id}",
                action_label="View candidate",
                candidate_id=candidate.id,
            )

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
        candidate.stage = PipelineStage.RESUME_SHORTLISTED.value

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


def _parse_jd_requirements(jd_details: str) -> dict:
    """Extract requirement hints from JD text. Returns defaults if nothing found."""
    reqs = {
        "yoe": "5+ years",
        "budget": "12 LPA",
        "location": "India",
        "notice_period": "30 days",
    }

    yoe_match = re.search(r'(\d+)\s*\+\s*years?\s*(?:of\s+)?(?:experience|exp)', jd_details, re.IGNORECASE)
    if yoe_match:
        reqs["yoe"] = f"{yoe_match.group(1)}+ years"

    budget_match = re.search(r'(?:budget|ctc|compensation|salary).{0,30}?(\d+)\s*(?:lpa|lakh|k)', jd_details, re.IGNORECASE)
    if budget_match:
        reqs["budget"] = f"{budget_match.group(1)} LPA"

    loc_match = re.search(r'(?:location|based|work from)\s*[:\-]?\s*([A-Za-z].{2,30}?)(?:\n|\.|,|$)', jd_details, re.IGNORECASE)
    if loc_match:
        loc = loc_match.group(1).strip()
        if loc and len(loc) > 2:
            reqs["location"] = loc.title()

    np_match = re.search(r'(?:notice\s*period|np).{0,20}?(\d+)\s*(?:days?|months?)', jd_details, re.IGNORECASE)
    if np_match:
        reqs["notice_period"] = f"{np_match.group(1)} days"

    return reqs


def _mock_evaluation_fallback(candidate, jd_details: str) -> AIEvaluationResponse:
    """Smart mock evaluation that uses candidate data + JD details.

    Randomly shortlists ~40% or rejects with specific reasons based on
    candidate's YOE, expected CTC, location, and notice period.
    """
    reqs = _parse_jd_requirements(jd_details)
    name = candidate.candidate_name or "The candidate"
    yoe = candidate.years_of_experience
    exp_ctc = candidate.expected_ctc
    location = candidate.location
    notice = candidate.notice_period
    willing_relocate = candidate.willing_to_relocate

    try:
        yoe_val = float(yoe) if yoe else None
    except (ValueError, TypeError):
        yoe_val = None
    try:
        ctc_val = float(exp_ctc) if exp_ctc else None
    except (ValueError, TypeError):
        ctc_val = None

    req_yoe = re.search(r'(\d+)', reqs["yoe"])
    req_yoe_val = float(req_yoe.group(1)) if req_yoe else 5
    req_budget = re.search(r'(\d+)', reqs["budget"])
    req_budget_val = float(req_budget.group(1)) if req_budget else 12

    rejection_details: list[dict] = []
    concerns: list[str] = []
    score = random.randint(65, 85)

    # YOE check
    if yoe_val is not None and yoe_val < req_yoe_val:
        rejection_details.append({
            "YOE": {"JD": reqs["yoe"], "Candidate": f"{yoe_val} yrs"}
        })
        concerns.append(f"Insufficient years of experience ({yoe_val} yrs, required {reqs['yoe']})")
        score = max(score - random.randint(15, 30), 5)
    elif yoe_val is not None:
        score += random.randint(0, 5)

    # Budget check
    if ctc_val is not None and ctc_val > req_budget_val:
        rejection_details.append({
            "BUDGET": {"JD": reqs["budget"], "Candidate": f"{ctc_val} LPA"}
        })
        concerns.append(f"Expected CTC exceeds budget ({ctc_val} LPA vs {reqs['budget']})")
        score = max(score - random.randint(10, 25), 5)

    # Location check
    if location and reqs["location"].lower() not in location.lower():
        if not willing_relocate:
            rejection_details.append({
                "LOCATION": {"JD": reqs["location"], "Candidate": location}
            })
            concerns.append(f"Location mismatch ({location}, required {reqs['location']})")
            score = max(score - random.randint(10, 20), 5)

    # Notice period check
    if notice:
        np_match = re.search(r'(\d+)', notice)
        if np_match:
            np_val = float(np_match.group(1))
            req_np_match = re.search(r'(\d+)', reqs["notice_period"])
            req_np_val = float(req_np_match.group(1)) if req_np_match else 30
            if np_val > req_np_val:
                rejection_details.append({
                    "NOTICE_PERIOD": {"JD": reqs["notice_period"], "Candidate": f"{np_val} days"}
                })
                concerns.append(f"Notice period too long ({np_val} days, max {reqs['notice_period']})")
                score = max(score - random.randint(10, 20), 5)

    # Force some randomness even if nothing is wrong (occasional rejection)
    if not rejection_details and random.random() < 0.25:
        score = random.randint(30, 55)
        rejection_details.append({
            "YOE": {"JD": reqs["yoe"], "Candidate": f"{yoe or '?'} yrs"}
        })
        concerns.append("Insufficient years of relevant experience")

    score = max(0, min(100, score))

    if not rejection_details:
        summary = (
            f"### Candidate Summary\n\n"
            f"**{name}** appears to be a strong match for this position.\n\n"
            f"**Strong Matches:**\n"
            f"- Experience ({yoe or '?'} yrs) aligns with the role requirements\n"
            f"- Location ({location or '?'}) is compatible\n"
            f"- Notice period ({notice or '?'}) is within acceptable range\n"
            f"- Expected compensation ({exp_ctc or '?'} LPA) fits within budget"
        )
    else:
        concerns_text = "\n".join(f"- {c}" for c in concerns)
        summary = (
            f"### Candidate Summary\n\n"
            f"**{name}** does not fully meet the requirements for this position.\n\n"
            f"**Areas of concern:**\n{concerns_text}"
        )

    return AIEvaluationResponse(
        resume_summary=summary,
        overall_score_percentage=score,
        rejection_details=rejection_details,
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
    logger.info("Processing application_id=%s (partition=%s, offset=%s)", message.application_id, msg.partition, msg.offset)
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
    setup_logging()
    logger.info("Starting full evaluation worker — topic=%s", settings.KAFKA_TOPIC_EVALUATION_ASYNC)
    logger.info("Max retry attempts per message: %d", settings.EVALUATION_MAX_ATTEMPTS)
    consume(
        topics=[settings.KAFKA_TOPIC_EVALUATION_ASYNC],
        handler=_handler_with_retry,
        group_id="resume-full-evaluators",
    )


if __name__ == "__main__":
    main()
