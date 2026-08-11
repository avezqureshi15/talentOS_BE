import hashlib
import hmac
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import InterviewStatus
from app.core.logger import get_logger
from app.core.secrets import get_secret
from app.db.session import get_db
from app.modules.interviews.interview_repository import InterviewRepository
from app.modules.interviews.review_questions_service import ReviewQuestionsService

logger = get_logger(__name__)

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/webhooks/meetmind", tags=["meetmind"])


class MeetMindTranscriptPayload(BaseModel):
    success: bool
    meetUrl: str = Field(..., min_length=1)
    transcription: Optional[str] = None
    errorCode: Optional[str] = None
    message: Optional[str] = None


def _verify_signature(raw_body: bytes, signature_header: str | None) -> None:
    secret = (get_secret("MEETMIND_WEBHOOK_SECRET") or "").encode("utf-8")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MeetMind webhook secret not configured",
        )
    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Signature header",
        )

    provided = signature_header.strip()
    expected_hex = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    expected = f"sha256={expected_hex}"
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-Signature",
        )


@router.post("/transcript", status_code=status.HTTP_200_OK)
async def meetmind_transcript_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(default=None, alias="X-Signature"),
):
    """MeetMind transcript webhook. Correlate by meetUrl; auth via X-Signature HMAC."""
    raw_body = await request.body()
    _verify_signature(raw_body, x_signature)

    try:
        payload = MeetMindTranscriptPayload.model_validate_json(raw_body)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid payload: {exc}",
        ) from exc

    if not payload.success:
        logger.info(
            "MeetMind webhook success=false | meet_url=%s errorCode=%s message=%s",
            payload.meetUrl,
            payload.errorCode,
            payload.message,
        )
        return {"status": "ignored", "reason": "success_false"}

    transcription = (payload.transcription or "").strip()
    if not transcription:
        logger.warning("MeetMind webhook success=true but empty transcription | meet_url=%s", payload.meetUrl)
        return {"status": "ignored", "reason": "empty_transcription"}

    interview = InterviewRepository(db).get_by_meet_link(payload.meetUrl)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No interview found for meetUrl={payload.meetUrl}",
        )

    # First success webhook: complete + forms. Late after fallback: refresh questions only.
    # Do not remove the fallback job here — one-shot jobs auto-expire, and removing while
    # APScheduler is processing the same job races and can kill the scheduler thread.
    send_forms = interview.status != InterviewStatus.COMPLETED.value

    ReviewQuestionsService(db).finalize_for_review(
        str(interview.id),
        transcription=transcription,
        send_forms=send_forms,
    )
    logger.info(
        "MeetMind webhook processed | interview_id=%s send_forms=%s",
        interview.id,
        send_forms,
    )
    return {"status": "ok", "interview_id": str(interview.id)}
