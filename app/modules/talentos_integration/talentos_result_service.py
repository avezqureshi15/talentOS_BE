"""Shared persistence + failure handling for AI screening/interview results.

Single source of truth used by:
  - the pull-based AI endpoints (ai_integration_router)
  - the webhook push endpoints (talentos_webhook_router)
  - the manual retry endpoints (ai_integration_router)

Everything is stored in the ``reviews`` JSONB (entity_type ai_screening /
ai_interview); ``round_verdict`` stays HR-driven.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import EvaluationStatus
from app.core.kafka import publish
from app.core.logger import get_logger
from app.modules.ai.interview_report_schema import InterviewReportMessage
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.events.event_schema import EventCreate
from app.modules.events.event_service import EventService
from app.modules.notifications.notification_model import NotificationType
from app.modules.notifications.notification_service import NotificationService
from app.modules.reviews.review_model import Review
from app.modules.reviews.review_repository import ReviewRepository
from app.modules.reviews.review_schema import ReviewUpdateByRound
from app.modules.reviews.review_service import ReviewService
from app.modules.rounds.round_model import Round

logger = get_logger(__name__)

_AI_VERDICT_MAP: dict[str, str] = {
    "pass": "shortlisted",
    "shortlisted": "shortlisted",
    "selected": "shortlisted",
    "fail": "rejected",
    "failed": "rejected",
    "rejected": "rejected",
}

SCREENING_FAILURE_OUTCOMES = frozenset(
    {"no_answer", "voicemail", "declined", "dropped", "failed"}
)

SCREENING_ACTIVE_STATUSES = frozenset(
    {"SCREENING_ROUND_SCHEDULED", "AI_SCREENING_EVALUATION_FAILED"}
)


def _is_screening_failure(result: dict) -> bool:
    call_status = (result.get("call_status") or "").lower()
    if call_status and call_status != "completed":
        return True
    outcome = (result.get("call_outcome") or "").lower()
    if outcome in SCREENING_FAILURE_OUTCOMES:
        return True
    if (result.get("result") or "").lower() == "needs_review" and not (result.get("transcript") or "").strip():
        return True
    return False


def _is_interview_failure(result: dict) -> bool:
    status = (result.get("status") or "").lower()
    if status == "assessment_failed":
        return True
    if status in ("completed", "assessed") and not (result.get("transcript") or "").strip():
        return True
    return False


def persist_screening_result(db: Session, round_id: uuid.UUID, result: dict) -> None:
    keys = [
        "call_status", "call_outcome", "ended_reason", "retry_count", "result",
        "summary", "transcript", "availability", "employment_status",
        "relevant_experience", "current_ctc", "expected_ctc", "notice_period",
        "location_preference", "communication_quality", "willingness_to_proceed",
        "created_at",
    ]
    payload = {k: result.get(k) for k in keys}
    payload["screening_call_id"] = result.get("id")
    payload["recording_key"] = result.get("recording_key")
    verdict = _AI_VERDICT_MAP.get(result.get("result") or "")
    ReviewService(db).upsert_review(
        round_id,
        ReviewUpdateByRound(entity_type="ai_screening", reviews=payload, verdict=verdict),
    )


def persist_interview_result(db: Session, round_obj: Round, result: dict) -> None:
    keys = [
        "status", "transcript", "transcript_segments", "summary", "transcript_summary",
        "overall_score", "technical_fit_score", "communication_score",
        "problem_solving_score", "experience_score", "role_alignment_score",
        "strengths", "weaknesses", "jd_fit", "final_recommendation",
        "interview_url", "created_at", "started_at", "completed_at",
        "recording_key",
    ]
    payload = {k: result.get(k) for k in keys}
    payload["unique_token"] = round_obj.rh_unique_token
    verdict = _AI_VERDICT_MAP.get(result.get("final_recommendation") or "")
    ReviewService(db).upsert_review(
        round_obj.id,
        ReviewUpdateByRound(entity_type="ai_interview", reviews=payload, verdict=verdict),
    )
    _enqueue_interview_report(round_obj.id)


def _enqueue_interview_report(round_id: uuid.UUID) -> None:
    """Queue the async rich-report transform for a persisted interview result.

    Best-effort: a Kafka outage must never fail the webhook/pull/retry path.
    The worker re-reads the review row from the DB and is idempotent
    (already-transformed rows are skipped).
    """
    try:
        publish(
            topic=settings.KAFKA_TOPIC_INTERVIEW_REPORT_ASYNC,
            key=str(round_id),
            value=InterviewReportMessage(round_id=round_id).model_dump_json(),
        )
        logger.info("Enqueued AI interview report transform for round_id=%s", round_id)
    except Exception as exc:
        logger.error("Failed to enqueue AI interview report for round_id=%s: %s", round_id, exc)


def resolve_screening_round(db: Session, body: dict) -> tuple[Candidate | None, uuid.UUID | None]:
    """Find the talentOS round for a screening webhook payload.

    Correlates via external_candidate_id first, then the screening call id.
    Returns (candidate, round_id).
    """
    external_candidate_id = body.get("external_candidate_id")
    screening_call_id = body.get("screening_call_id")

    candidate: Candidate | None = None
    if external_candidate_id:
        candidate = (
            db.query(Candidate)
            .filter(Candidate.rh_external_candidate_id == external_candidate_id)
            .first()
        )
    if candidate is None and screening_call_id:
        candidate = (
            db.query(Candidate)
            .filter(Candidate.rh_external_screening_call_id == screening_call_id)
            .first()
        )
    if candidate is None:
        logger.warning(
            "talentOS screening webhook: no matching candidate (external_candidate_id=%s screening_call_id=%s)",
            external_candidate_id,
            screening_call_id,
        )
        return None, None
    return candidate, candidate.current_round_id


def resolve_interview_round(db: Session, body: dict) -> tuple[Candidate | None, Round | None]:
    """Find the talentOS round for an interview webhook payload.

    Correlates via rh_external_session_id first, then the candidate's current
    round. Returns (candidate, round_obj).
    """
    interview_id = body.get("interview_id")
    external_candidate_id = body.get("external_candidate_id")

    round_obj: Round | None = None
    if interview_id:
        round_obj = (
            db.query(Round).filter(Round.rh_external_session_id == interview_id).first()
        )

    candidate: Candidate | None = None
    if round_obj is None and external_candidate_id:
        candidate = (
            db.query(Candidate)
            .filter(Candidate.rh_external_candidate_id == external_candidate_id)
            .first()
        )
        if candidate and candidate.current_round_id:
            round_obj = db.query(Round).filter(Round.id == candidate.current_round_id).first()
    if round_obj is not None and candidate is None:
        candidate = (
            db.query(Candidate).filter(Candidate.id == round_obj.candidate_id).first()
            if round_obj.candidate_id else None
        )
    if round_obj is None:
        logger.warning(
            "talentOS interview webhook: no matching round (interview_id=%s external_candidate_id=%s)",
            interview_id,
            external_candidate_id,
        )
        return candidate, None
    return candidate, round_obj


def _notify_ai_failure(
    db: Session,
    *,
    hiring_request_id: uuid.UUID,
    round_id: uuid.UUID,
    candidate_id: int | None,
    entity_type: str,
    round_name: str | None,
    title: str,
    body: str,
    notification_type: str = NotificationType.EVALUATION_FAILED.value,
    event_name: str = "AI Evaluation Failed",
    state_code: str = "AI_EVALUATION_FAILED",
    dedupe_key: str | None = None,
) -> None:
    NotificationService(db).notify_job_team_and_admins(
        hiring_request_id,
        notification_type=notification_type,
        title=title,
        body=body,
        action_url=f"/hiring-requests/{hiring_request_id}/candidates/{candidate_id}" if candidate_id else None,
        action_label="View candidate" if candidate_id else None,
        candidate_id=candidate_id,
        dedupe_key=dedupe_key or f"AI_FAILED-{round_id}",
    )
    EventService(db).create_event(EventCreate(
        entity_type="CANDIDATE",
        entity_id=str(candidate_id) if candidate_id else str(round_id),
        job_id=hiring_request_id,
        candidate_id=candidate_id,
        event_name=event_name,
        state_code=state_code,
        actor_type="SYSTEM",
        event_metadata={
            "round_id": str(round_id),
            "entity_type": entity_type,
            "round_name": round_name,
        },
    ))


def apply_screening_flag(
    db: Session,
    round_id: uuid.UUID,
    candidate: Candidate | None,
    status_info: dict,
) -> None:
    """Persist an AI screening flag and move the candidate to the flagged state.

    The POC classifies a candidate as "flagged" when screening can never
    complete (missing/invalid phone, declined, technical failure, or exhausted
    dial attempts). talentOS records the flag in the ``reviews`` JSONB
    (entity_type ``ai_screening``, verdict ``flagged``), moves the candidate to
    ``AI_SCREENING_FLAGGED`` (stage stays ``AI_SCREENING``) and notifies the job
    team (deduped per round).

    ``round_verdict`` is intentionally left untouched — it stays HR-driven. The
    review row is written directly through the repository (not
    ReviewService.upsert_review) so the round-verdict recompute is not triggered.
    Idempotent: a re-run on a candidate already in AI_SCREENING_FLAGGED only
    refreshes the persisted flag payload.
    """
    if candidate is None:
        return

    if candidate.status != EvaluationStatus.AI_SCREENING_FLAGGED.value:
        candidate.stage = "AI_SCREENING"
        candidate.status = EvaluationStatus.AI_SCREENING_FLAGGED.value
        db.commit()
        logger.info(
            "AI screening marked flagged | candidate_id=%s round_id=%s reason=%s",
            candidate.id, round_id, status_info.get("flag_reason"),
        )

    flag_reason = status_info.get("flag_reason")
    latest_call = status_info.get("latest_call") or {}
    payload = {
        "flagged": True,
        "flag_reason": flag_reason,
        "disposition": "flagged",
        "screening_call_id": latest_call.get("id"),
        "flagged_at": datetime.now(timezone.utc).isoformat(),
    }
    repo = ReviewRepository(db)
    review = repo.get_by_round_and_entity(round_id, "ai_screening")
    if review is not None:
        review.reviews = payload
        review.verdict = "flagged"
        repo.update(review)
    else:
        review = Review(
            round_id=round_id,
            entity_type="ai_screening",
            reviews=payload,
            verdict="flagged",
        )
        repo.create(review)
    db.commit()

    round_obj = db.query(Round).filter(Round.id == round_id).first() if round_id else None
    if round_obj and round_obj.jd_id:
        _notify_ai_failure(
            db,
            hiring_request_id=round_obj.jd_id,
            round_id=round_id,
            candidate_id=candidate.id,
            entity_type="ai_review",
            round_name=round_obj.name,
            title="AI screening flagged for a candidate",
            body=(
                f"AI screening round \"{round_obj.name or round_id}\" was flagged and could not "
                f"complete. Reason: {flag_reason or 'unknown'}. Review the candidate from the "
                "AI screening section."
            ),
            notification_type=NotificationType.AI_SCREENING_FLAGGED.value,
            event_name="AI Screening Flagged",
            state_code=EvaluationStatus.AI_SCREENING_FLAGGED.value,
            dedupe_key=f"AI_FLAGGED-{round_id}",
        )


def apply_screening_outcome(
    db: Session,
    round_id: uuid.UUID,
    candidate: Candidate | None,
    result: dict,
) -> None:
    """Apply a screening result to the candidate's pipeline state.

    Failure (terminal): stage stays ``AI_SCREENING`` and status becomes
    ``AI_SCREENING_EVALUATION_FAILED`` so the candidate remains in the
    screening pipeline for retry; sends the EVALUATION_FAILED notification
    and AI_EVALUATION_FAILED event (deduped per round).

    Success: ``SCREENING_ROUND_SCHEDULED`` / ``AI_SCREENING_EVALUATION_FAILED``
    -> ``UNDER_EVALUATION`` while retaining stage ``AI_SCREENING`` (the stage
    is never renamed for AI screening — only the status changes), so a re-run
    after failure recovers the candidate.

    Payloads pulled from the POC carry ``terminal_failure`` (authoritative —
    retries may still be pending otherwise). Webhook push payloads don't, so
    they fall back to the legacy ``_is_screening_failure`` check.
    """
    if result.get("terminal_failure") is None:
        is_failure = _is_screening_failure(result)
    else:
        is_failure = bool(result.get("terminal_failure"))

    if candidate is None:
        return

    if is_failure:
        if candidate.stage == "AI_SCREENING" or candidate.status in SCREENING_ACTIVE_STATUSES:
            if candidate.status != EvaluationStatus.AI_SCREENING_EVALUATION_FAILED.value:
                candidate.status = EvaluationStatus.AI_SCREENING_EVALUATION_FAILED.value
                candidate.stage = "AI_SCREENING"
                db.commit()
                logger.info(
                    "AI screening marked failed | candidate_id=%s round_id=%s",
                    candidate.id, round_id,
                )
        round_obj = db.query(Round).filter(Round.id == round_id).first() if round_id else None
        if round_obj and round_obj.jd_id:
            _notify_ai_failure(
                db,
                hiring_request_id=round_obj.jd_id,
                round_id=round_id,
                candidate_id=candidate.id,
                entity_type="ai_screening",
                round_name=round_obj.name,
                title="AI screening failed for a candidate",
                body=(
                    f"AI screening round \"{round_obj.name or round_id}\" did not complete. "
                    f"Status: {result.get('call_status') or 'unknown'}. "
                    "You can retry from the candidate's AI screening section."
                ),
            )
        return

    if candidate.status not in SCREENING_ACTIVE_STATUSES:
        return

    candidate.stage = "AI_SCREENING"
    candidate.status = EvaluationStatus.UNDER_EVALUATION.value
    db.commit()
    EventService(db).create_event(EventCreate(
        entity_type="CANDIDATE",
        entity_id=str(candidate.id),
        candidate_id=candidate.id,
        event_name="AI Screening Completed",
        state_code=EvaluationStatus.UNDER_EVALUATION.value,
        actor_type="SYSTEM",
        event_metadata={"round_id": str(round_id)},
    ))
    logger.info(
        "AI screening completed | candidate_id=%s round_id=%s new_status=%s",
        candidate.id, round_id, EvaluationStatus.UNDER_EVALUATION.value,
    )


def handle_screening_webhook(db: Session, body: dict) -> dict:
    result = body.get("result") or {}
    candidate, round_id = resolve_screening_round(db, body)
    if round_id is None:
        return {"status": "ignored", "reason": "no matching candidate or round"}

    persist_screening_result(db, round_id, result)
    apply_screening_outcome(db, round_id, candidate, result)

    return {
        "status": "received",
        "round_id": str(round_id),
        "screening_call_id": body.get("screening_call_id"),
    }


def handle_interview_webhook(db: Session, body: dict) -> dict:
    result = body.get("result") or {}
    candidate, round_obj = resolve_interview_round(db, body)
    if round_obj is None:
        return {"status": "ignored", "reason": "no matching round or candidate"}

    persist_interview_result(db, round_obj, result)

    if _is_interview_failure(result) and round_obj.jd_id:
        _notify_ai_failure(
            db,
            hiring_request_id=round_obj.jd_id,
            round_id=round_obj.id,
            candidate_id=round_obj.candidate_id,
            entity_type="ai_interview",
            round_name=round_obj.name,
            title="AI interview assessment failed",
            body=(
                f"AI interview round \"{round_obj.name or round_obj.id}\" could not be assessed "
                f"(status: {result.get('status') or 'unknown'}). "
                "You can retry the assessment from the AI interview view."
            ),
        )

    return {
        "status": "received",
        "round_id": str(round_obj.id),
        "interview_id": body.get("interview_id"),
    }
