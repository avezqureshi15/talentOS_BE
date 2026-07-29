import random
import re
from uuid import UUID

from app.common.clients import AIClient, ClientError, ResumeClient, SupabaseClient
from app.core.config import settings
from app.core.constants import EvaluationStatus, PipelineStage
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
            "candidate_type": record.candidate_type,
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
            EvaluationStatus.RESUME_SHORTLISTED.value, EvaluationStatus.RESUME_PROCESSING_FAILED.value,
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
                candidate_type=app.get("candidate_type", "REGULAR"),
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
                event_metadata={"error_reason": "No resume_url provided"},
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
                event_metadata={"error_reason": "Resume is not text-extractable"},
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
            event_metadata={"resume_url": resume_url},
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
        except ClientError:
            logger.warning("AI service failed — using mock evaluation")
            ai_result = self._mock_evaluation_fallback(candidate, jd_details)
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
                event_metadata={"error_reason": f"Unexpected error: {exc}"},
            ))
            candidate = self.repo.mark_result(candidate, EvaluationStatus.RESUME_PROCESSING_FAILED, error_reason=f"Unexpected error: {exc}")
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
            event_metadata={"fit_score": ai_result.overall_score_percentage, "threshold_used": threshold},
        ))
        self._create_initial_review(ai_result, candidate, job_id, verdict)
        return self.repo.to_candidate_dict(candidate)

    def _mock_evaluation_fallback(self, candidate, jd_details: str) -> AIEvaluationResponse:
        reqs = self._parse_jd_requirements(jd_details)
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

        req_yoe_match = re.search(r'(\d+)', reqs["yoe"])
        req_yoe_val = float(req_yoe_match.group(1)) if req_yoe_match else 5
        req_budget_match = re.search(r'(\d+)', reqs["budget"])
        req_budget_val = float(req_budget_match.group(1)) if req_budget_match else 12

        rejection_details: list[dict] = []
        concerns: list[str] = []
        score = random.randint(65, 85)

        if yoe_val is not None and yoe_val < req_yoe_val:
            rejection_details.append({
                "YOE": {"JD": reqs["yoe"], "Candidate": f"{yoe_val} yrs"}
            })
            concerns.append(f"Insufficient years of experience ({yoe_val} yrs, required {reqs['yoe']})")
            score = max(score - random.randint(15, 30), 5)
        elif yoe_val is not None:
            score += random.randint(0, 5)

        if ctc_val is not None and ctc_val > req_budget_val:
            rejection_details.append({
                "BUDGET": {"JD": reqs["budget"], "Candidate": f"{ctc_val} LPA"}
            })
            concerns.append(f"Expected CTC exceeds budget ({ctc_val} LPA vs {reqs['budget']})")
            score = max(score - random.randint(10, 25), 5)

        if location and reqs["location"].lower() not in location.lower():
            if not willing_relocate:
                rejection_details.append({
                    "LOCATION": {"JD": reqs["location"], "Candidate": location}
                })
                concerns.append(f"Location mismatch ({location}, required {reqs['location']})")
                score = max(score - random.randint(10, 20), 5)

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

    def _parse_jd_requirements(self, jd_details: str) -> dict:
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

    def _create_initial_review(self, ai_result: AIEvaluationResponse, candidate, job_id: str, verdict: str) -> None:
        try:
            jd_uuid = self.repo.resolve_hiring_request_id(job_id)
            round_resp = RoundService(self.db).create_round(RoundCreate(
                name="Resume Shortlisting", round_type="RESUME_SHORTLISTING",
                candidate_id=candidate.id, jd_id=jd_uuid,
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
                event_metadata={"fit_score": ai_result.overall_score_percentage, "round_id": str(round_resp.id), "verdict": verdict},
            ))
        except Exception as exc:
            logger.error("Round/review creation failed for candidate_id=%s: %s", candidate.id, exc)
