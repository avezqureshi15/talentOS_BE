from sqlalchemy.orm import Session

from app.modules.evaluations.evaluation_model import Candidate
from app.modules.reviews.review_model import Review


def get_ai_review(db: Session, candidate: Candidate, review_map: dict[str, Review] | None = None) -> dict | None:
    if not candidate.current_round_id:
        return None
    if review_map:
        rv = review_map.get(str(candidate.current_round_id))
        if rv and rv.reviews:
            return {"reviews": rv.reviews, "verdict": rv.verdict}
    rv = (
        db.query(Review)
        .filter(
            Review.round_id == candidate.current_round_id,
            Review.entity_type == "AI",
        )
        .first()
    )
    if rv:
        return {"reviews": rv.reviews, "verdict": rv.verdict}
    return None


def build_candidate_response(
    candidate: Candidate,
    ai_review: dict | None = None,
    hide_cover_letter: bool = False,
    events: list[dict] | None = None,
    active_interview: dict | None = None,
) -> dict:
    return {
        "id": candidate.external_application_id,
        "candidate_id": candidate.id,
        "job_id": candidate.external_job_id,
        "name": candidate.candidate_name,
        "email": candidate.candidate_email,
        "phone": candidate.candidate_phone,
        "cover_letter": None if hide_cover_letter else candidate.cover_letter,
        "resume_url": candidate.resume_url,
        "current_ctc": candidate.current_ctc,
        "expected_ctc": candidate.expected_ctc,
        "location": candidate.location,
        "years_of_experience": candidate.years_of_experience,
        "notice_period": candidate.notice_period,
        "how_did_you_hear": candidate.how_did_you_hear,
        "linkedin_url": candidate.linkedin_url,
        "willing_to_relocate": candidate.willing_to_relocate if candidate.willing_to_relocate is not None else False,
        "status": candidate.status,
        "fit_score": candidate.fit_score,
        "summary_md": candidate.summary_md,
        "evaluated_at": candidate.evaluated_at.isoformat() if candidate.evaluated_at else None,
        "scheduled": candidate.scheduled,
        "current_round_id": str(candidate.current_round_id) if candidate.current_round_id else None,
        "final_verdict": candidate.final_verdict,
        "reviews": (ai_review or {}).get("reviews"),
        "review_verdict": (ai_review or {}).get("verdict"),
        "events": events,
        "active_interview": active_interview,
    }
