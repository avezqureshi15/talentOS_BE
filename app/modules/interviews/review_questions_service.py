import uuid

from sqlalchemy.orm import Session

from app.common.clients.ai_client import AIClient
from app.common.schemas.review_questions import ReviewPhase, ReviewQuestionsPayload
from app.core.constants import EvaluationStatus, InterviewStatus
from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.events.event_schema import EventCreate
from app.modules.events.event_service import EventService
from app.modules.forms.form_repository import FormRepository
from app.modules.forms.form_service import FormService
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.interviews.interview_repository import InterviewRepository
from app.modules.interviews.models.interview import Interview
from app.modules.interviews.review_questions_constants import (
    STATIC_REVIEW_PHASES,
    STATIC_REVIEW_QUESTIONS_SOURCE,
)
from app.modules.rounds.round_model import Round

logger = get_logger(__name__)

_SOURCE_TRANSCRIPT = "transcript"
_SOURCE_JD = "jd"

_ACTIVE_STATUSES = (InterviewStatus.SCHEDULED.value, InterviewStatus.RESCHEDULED.value)


class ReviewQuestionsService:
    def __init__(self, db: Session, ai: AIClient | None = None):
        self.db = db
        self.repository = InterviewRepository(db)
        self.ai = ai or AIClient()

    def get_questions_for_round(self, round_id: uuid.UUID) -> ReviewQuestionsPayload:
        """Return interview review questions for a round, or static fallback."""
        interview = self.repository.get_by_round_id(round_id)
        if interview and interview.review_questions:
            raw_phases = interview.review_questions.get("phases") or []
            phases: list[ReviewPhase] = []
            for item in raw_phases:
                if not isinstance(item, dict):
                    continue
                phase_name = (item.get("phase") or "").strip()
                questions = item.get("questions") or []
                if not phase_name or not isinstance(questions, list):
                    continue
                cleaned = [str(q).strip() for q in questions if str(q).strip()]
                if cleaned:
                    phases.append(ReviewPhase(phase=phase_name, questions=cleaned))
            if phases:
                source = (interview.review_questions_source or "").strip() or _SOURCE_JD
                return ReviewQuestionsPayload(questions_source=source, phases=phases)

        logger.info("Using static review questions | round_id=%s", round_id)
        return ReviewQuestionsPayload(
            questions_source=STATIC_REVIEW_QUESTIONS_SOURCE,
            phases=list(STATIC_REVIEW_PHASES),
        )

    def finalize_for_review(
        self,
        interview_id: str,
        *,
        transcription: str | None,
        send_forms: bool,
    ) -> None:
        """Complete interview if needed, generate review questions, optionally email forms.

        Shared by MeetMind webhook and the interview fallback job.

        Idempotency:
        - Already COMPLETED + no transcript (fallback after webhook): full no-op.
        - Already COMPLETED + transcript (late webhook after fallback): refresh
          questions only; never re-mark status or re-send forms.
        """
        interview = self.repository.get_by_id(uuid.UUID(interview_id))
        if not interview:
            logger.info("Finalize skipped | interview not found | interview_id=%s", interview_id)
            return

        already_completed = interview.status == InterviewStatus.COMPLETED.value
        transcription = (transcription or "").strip() or None

        # Fallback after webhook already finalized: do not touch status, AI, or forms.
        if already_completed and not transcription:
            logger.info(
                "Finalize skipped | already completed, no transcript refresh | interview_id=%s",
                interview_id,
            )
            return

        if interview.status in _ACTIVE_STATUSES:
            self._mark_completed(interview)
            interview = self.repository.get_by_id(interview.id)
            if not interview:
                return
        elif not already_completed:
            logger.info(
                "Finalize skipped | unexpected status=%s interview_id=%s",
                interview.status,
                interview_id,
            )
            return

        round_ = self.repository.get_round_by_id(interview.round_id)
        candidate_id = round_.candidate_id if round_ else None

        # Late webhook after fallback: refresh questions from transcript, do not re-mail.
        if already_completed:
            send_forms = False

        self._generate_questions(interview, round_, transcription=transcription)
        if send_forms:
            self._send_review_forms(round_, candidate_id)

    def _mark_completed(self, interview: Interview) -> None:
        interview_id = str(interview.id)
        round_ = self.repository.get_round_by_id(interview.round_id)
        candidate_id = round_.candidate_id if round_ else None

        interview.status = InterviewStatus.COMPLETED.value

        if candidate_id:
            self.db.query(Candidate).filter(Candidate.id == candidate_id).update(
                {"status": EvaluationStatus.WAITING_FOR_REVIEW.value}
            )
            EventService(self.db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate_id),
                event_name="Interview Completed",
                state_code=EvaluationStatus.INTERVIEW_COMPLETED.value,
                actor_type="SYSTEM",
                candidate_id=candidate_id,
                event_metadata={
                    "interview_id": interview_id,
                    "round_id": str(interview.round_id),
                    "round_name": round_.name if round_ else None,
                },
            ))
            EventService(self.db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate_id),
                event_name="Waiting For Review",
                state_code=EvaluationStatus.WAITING_FOR_REVIEW.value,
                actor_type="SYSTEM",
                candidate_id=candidate_id,
                event_metadata={
                    "interview_id": interview_id,
                    "round_id": str(interview.round_id),
                    "round_name": round_.name if round_ else None,
                },
            ))

        self.db.commit()
        logger.info(
            "Interview marked completed | interview_id=%s candidate_id=%s",
            interview_id,
            candidate_id,
        )

    def _generate_questions(
        self,
        interview: Interview,
        round_: Round | None,
        *,
        transcription: str | None,
    ) -> None:
        interview_id = str(interview.id)
        try:
            if transcription:
                response = self.ai.generate_review_questions(transcription=transcription)
                self.repository.save_review_questions(
                    interview_id=interview.id,
                    transcript_text=transcription,
                    review_questions=response.model_dump(),
                    source=_SOURCE_TRANSCRIPT,
                )
                self.db.commit()
                logger.info("Review questions saved from transcript | interview_id=%s", interview_id)
                return

            if interview.review_questions is not None:
                logger.info("Review questions already present | interview_id=%s", interview_id)
                return

            jd_details = self._build_jd_text(round_)
            if jd_details:
                response = self.ai.generate_review_questions(jd_details=jd_details)
                self.repository.save_review_questions(
                    interview_id=interview.id,
                    transcript_text=None,
                    review_questions=response.model_dump(),
                    source=_SOURCE_JD,
                )
                self.db.commit()
                logger.info("Review questions saved from JD | interview_id=%s", interview_id)
            else:
                logger.warning(
                    "No transcript and no JD for review questions; FE static fallback | interview_id=%s",
                    interview_id,
                )
        except Exception:
            logger.exception("Review questions generation failed | interview_id=%s", interview_id)
            self.db.rollback()

    def _build_jd_text(self, round_: Round | None) -> str | None:
        if not round_ or not round_.jd_id:
            return None
        hiring_request = self.repository.get_hiring_request_by_id(round_.jd_id)
        if not hiring_request:
            return None
        return _format_hiring_request_jd(hiring_request)

    def _send_review_forms(self, round_: Round | None, candidate_id: int | None) -> None:
        if not round_ or not candidate_id:
            logger.warning(
                "Review forms skipped | missing round or candidate_id | round_id=%s candidate_id=%s",
                getattr(round_, "id", None),
                candidate_id,
            )
            return

        candidate = self.db.query(Candidate).filter(Candidate.id == candidate_id).first()
        candidate_name = candidate.candidate_name if candidate else "Candidate"
        round_name = round_.name or "Interview"

        # Forms + mail key off employees.id; do not require a linked users row.
        interviewers = self.repository.get_interviewer_employees_for_round(round_.id)
        if not interviewers:
            logger.warning(
                "Review forms skipped | no interviewer employees on round | round_id=%s",
                round_.id,
            )
            return

        for employee in interviewers:
            try:
                form_db = SessionLocal()
                try:
                    active = FormRepository(form_db).get_active_sent_by_employee_and_round(
                        employee.id,
                        round_.id,
                    )
                    if active:
                        logger.info(
                            "Skipping review form; active form exists | emp_id=%s employee_id=%s round_id=%s form_id=%s",
                            employee.emp_id,
                            employee.id,
                            round_.id,
                            active.id,
                        )
                        continue
                    form = FormService(form_db).generate_review_form(
                        emp_id=employee.emp_id,
                        round_id=round_.id,
                        candidate_id=candidate_id,
                        candidate_name=candidate_name,
                        round_name=round_name,
                        interviewer_name=employee.name or employee.emp_id,
                        interviewer_email=employee.email or "",
                    )
                    logger.info(
                        "Review form sent | emp_id=%s employee_id=%s round_id=%s form_id=%s",
                        employee.emp_id,
                        employee.id,
                        round_.id,
                        form.id,
                    )
                finally:
                    form_db.close()
            except Exception as exc:
                logger.error(
                    "Failed to send review form | emp_id=%s employee_id=%s | %s",
                    employee.emp_id,
                    employee.id,
                    exc,
                )



def _format_hiring_request_jd(hiring_request: HiringRequest) -> str:
    requirements = hiring_request.requirements or []
    req_text = (
        "\n".join(f"- {r}" for r in requirements)
        if isinstance(requirements, list)
        else str(requirements)
    )
    return (
        f"Title: {hiring_request.title}\n\n"
        f"Description:\n{hiring_request.description}\n\n"
        f"Requirements:\n{req_text}"
    ).strip()
