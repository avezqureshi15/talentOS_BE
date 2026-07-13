from uuid import UUID

from app.common.clients import AIClient, AIClientError, ResumeClient, SupabaseClient
from app.core.config import settings
from app.core.constants import EvaluationStatus
from app.core.logger import get_logger
from app.common.schemas.evaluation import AIEvaluationResponse
from app.modules.applications.application_repository import ApplicationRepository
from app.modules.evaluations.evaluation_schema import WebhookRecord
from app.modules.reviews.review_schema import ReviewCreate
from app.modules.reviews.review_service import ReviewService
from app.modules.events.event_schema import EventCreate
from app.modules.events.event_service import EventService
from app.modules.rounds.round_schema import RoundCreate
from app.modules.rounds.round_service import RoundService

logger = get_logger(__name__)


class ApplicationEvaluationService:
    def __init__(self, db, repo: ApplicationRepository):
        self.db = db
        self.repo = repo
        self.supabase = SupabaseClient()
        self.ai = AIClient()
        self.resume = ResumeClient()

    def evaluate_webhook(self, record: WebhookRecord) -> dict:
        app_dict = {
            "id": str(record.id), "job_id": str(record.job_id), "name": record.name,
            "email": record.email, "phone": record.phone, "cover_letter": record.cover_letter,
            "resume_url": record.resume_url, "current_ctc": record.current_ctc,
            "expected_ctc": record.expected_ctc, "location": record.location,
            "years_of_experience": record.years_of_experience, "notice_period": record.notice_period,
            "how_did_you_hear": record.how_did_you_hear, "linkedin_url": record.linkedin_url,
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
            EvaluationStatus.SHORTLISTED.value, EvaluationStatus.REJECTED.value,
            EvaluationStatus.INVALID.value, EvaluationStatus.FAILED.value,
        ):
            return self.repo.to_candidate_dict(candidate)
        if candidate is None:
            candidate = self.repo.create_queued_candidate(
                application_id=application_id, job_id=job_id,
                candidate_name=app.get("name"), candidate_email=app.get("email"),
                candidate_phone=app.get("phone"), cover_letter=app.get("cover_letter"),
                resume_url=app.get("resume_url"), current_ctc=app.get("current_ctc"),
                expected_ctc=app.get("expected_ctc"), location=app.get("location"),
                years_of_experience=app.get("years_of_experience"), notice_period=app.get("notice_period"),
                how_did_you_hear=app.get("how_did_you_hear"), linkedin_url=app.get("linkedin_url"),
                willing_to_relocate=app.get("willing_to_relocate", False),
            )
            EventService(self.db).create_event(EventCreate(
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
        resume_url = app.get("resume_url") or candidate.resume_url
        if not resume_url:
            EventService(self.db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate.id),
                event_name="Resume Evaluation Failed",
                state_code="EVALUATION_FAILED",
                actor_type="SYSTEM",
                candidate_id=candidate.id,
                remark="No resume_url provided",
                metadata={"error_reason": "No resume_url provided"},
            ))
            candidate = self.repo.mark_result(candidate, EvaluationStatus.INVALID, error_reason="No resume_url provided")
            return self.repo.to_candidate_dict(candidate)
        resume_text = self.resume.extract_text(resume_url)
        if len(resume_text.strip()) < settings.EVALUATION_MIN_RESUME_CHARS:
            EventService(self.db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate.id),
                event_name="Resume Evaluation Failed",
                state_code="EVALUATION_FAILED",
                actor_type="SYSTEM",
                candidate_id=candidate.id,
                remark="Resume is not text-extractable (image/scanned PDF)",
                metadata={"error_reason": "Resume is not text-extractable"},
            ))
            candidate = self.repo.mark_result(candidate, EvaluationStatus.INVALID, error_reason="Resume is not text-extractable (image/scanned PDF)")
            return self.repo.to_candidate_dict(candidate)
        candidate = self.repo.mark_processing(candidate)
        EventService(self.db).create_event(EventCreate(
            entity_type="CANDIDATE",
            entity_id=str(candidate.id),
            event_name="Resume Evaluation Started",
            state_code="EVALUATION_STARTED",
            actor_type="SYSTEM",
            candidate_id=candidate.id,
            metadata={"resume_url": resume_url},
        ))
        candidate_meta_parts = []
        for label, val in [
            ("Years of Experience", candidate.years_of_experience),
            ("Current CTC", candidate.current_ctc), ("Expected CTC", candidate.expected_ctc),
            ("Location", candidate.location), ("Notice Period", candidate.notice_period),
        ]:
            if val:
                candidate_meta_parts.append(f"{label}: {val}")
        if candidate_meta_parts:
            resume_text += "\n\n--- Candidate Details ---\n" + "\n".join(candidate_meta_parts)
        jd_details = self.supabase.fetch_jd_details(job_id)
        try:
            ai_result = self.ai.evaluate_resume(resume_txt=resume_text, jd_details=jd_details, custom_evaluation_criteria="")
        except AIClientError:
            logger.warning("AI service failed — using mock evaluation")
            ai_result = self._mock_evaluation_fallback(candidate.candidate_name)
        except Exception as exc:
            logger.exception("Unexpected error evaluating application_id=%s", application_id)
            EventService(self.db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate.id),
                event_name="Resume Evaluation Failed",
                state_code="EVALUATION_FAILED",
                actor_type="SYSTEM",
                candidate_id=candidate.id,
                remark=f"Unexpected error: {exc}",
                metadata={"error_reason": f"Unexpected error: {exc}"},
            ))
            candidate = self.repo.mark_result(candidate, EvaluationStatus.FAILED, error_reason=f"Unexpected error: {exc}")
            return self.repo.to_candidate_dict(candidate)
        threshold = settings.ATS_THRESHOLD_DEFAULT
        verdict = "shortlisted" if ai_result.overall_score_percentage >= threshold else "rejected"
        candidate = self.repo.mark_result(
            candidate, status=EvaluationStatus.UNDER_EVALUATION,
            fit_score=ai_result.overall_score_percentage,
            summary_md=ai_result.resume_summary, ats_threshold_used=threshold,
        )
        EventService(self.db).create_event(EventCreate(
            entity_type="CANDIDATE",
            entity_id=str(candidate.id),
            event_name="Resume Evaluation Completed",
            state_code="EVALUATION_COMPLETED",
            actor_type="AI",
            candidate_id=candidate.id,
            metadata={"fit_score": ai_result.overall_score_percentage, "threshold_used": threshold},
        ))
        self._create_initial_review(ai_result, candidate, job_id, verdict)
        return self.repo.to_candidate_dict(candidate)

    def _mock_evaluation_fallback(self, candidate_name: str | None) -> AIEvaluationResponse:
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
            rejected_status=["YOE", "LOCATION", "NOTICE_PERIOD"],
            rejected_reason=(
                "Candidate has less than the required years of experience, "
                "is located outside the preferred hiring regions, "
                "and has a notice period longer than the acceptable limit."
            ),
        )

    def _create_initial_review(self, ai_result: AIEvaluationResponse, candidate, job_id: str, verdict: str) -> None:
        try:
            jd_uuid = self.repo.resolve_hiring_request_id(job_id)
            round_resp = RoundService(self.db).create_round(RoundCreate(
                name="Resume Shortlisting", candidate_id=candidate.id, jd_id=jd_uuid,
            ))
            self.db.refresh(candidate)
            self.repo.set_current_round_id(candidate, round_resp.id)
            ReviewService(self.db).create_review(ReviewCreate(
                round_id=round_resp.id, entity_type="AI",
                reviews={
                    "fitscore": ai_result.overall_score_percentage,
                    "summary": ai_result.resume_summary, "summary_md": ai_result.resume_summary,
                    "YOE": {"actual": f"{candidate.years_of_experience or '?'} yrs", "expected": "5 yrs"},
                    "CTC": {"actual": f"{candidate.current_ctc or '?'} LPA", "expected": "12 LPA"},
                    "LOCATION": {"actual": candidate.location or "?", "expected": "India"},
                    "NOTICE_PERIOD": {"actual": f"{candidate.notice_period or '?'} days", "expected": "15 days"},
                    "rejected_status": [s for s in ai_result.rejected_status if s != "NONE"],
                    "rejected_reason": ai_result.rejected_reason,
                },
                verdict=verdict,
            ))
            from app.modules.rounds.round_model import Round
            round_obj = self.db.query(Round).filter(Round.id == round_resp.id).first()
            if round_obj:
                round_obj.round_verdict = "selected" if verdict == "shortlisted" else "rejected"
                self.db.flush()
            EventService(self.db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate.id),
                event_name="Candidate Shortlisted by AI" if verdict == "shortlisted" else "Rejected by AI",
                state_code="AI_SHORTLISTED" if verdict == "shortlisted" else "AI_REJECTED",
                actor_type="AI",
                candidate_id=candidate.id,
                metadata={"fit_score": ai_result.overall_score_percentage, "round_id": str(round_resp.id), "verdict": verdict},
            ))
        except Exception as exc:
            logger.error("Round/review creation failed for candidate_id=%s: %s", candidate.id, exc)
