from app.modules.evaluations.evaluation_model import Candidate


def extract_comparison_fields(reviews: dict | None) -> list[dict]:
    if not reviews:
        return []
    result: list[dict] = []
    for k, v in reviews.items():
        if isinstance(v, dict) and "actual" in v and "expected" in v:
            result.append({
                "label": k,
                "value": {"Expected": str(v["expected"]), "Actual": str(v["actual"])},
            })
    return result


def build_candidate_response(candidate: Candidate, hide_cover_letter: bool = False, events: list[dict] | None = None, interview_data: dict | None = None) -> dict:
    result = {
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
        "candidate_type": candidate.candidate_type,
        "status": candidate.status,
        "stage": candidate.stage,
        "fit_score": candidate.fit_score,
        "summary_md": candidate.summary_md,
        "evaluated_at": candidate.evaluated_at.isoformat() if candidate.evaluated_at else None,
        "scheduled": candidate.scheduled,
        "current_round_id": str(candidate.current_round_id) if candidate.current_round_id else None,
        "final_verdict": candidate.final_verdict,
        "reviews": candidate.reviews,
        "review_verdict": candidate.review_verdict,
        "comparison_fields": extract_comparison_fields(candidate.reviews),
        "events": events,
        "interview_id": None,
        "interviewer_emp_id": None,
        "interviewer_name": None,
        "round_name": None,
    }
    if interview_data:
        result["interview_id"] = interview_data.get("interview_id")
        result["interviewer_emp_id"] = interview_data.get("interviewer_emp_id")
        result["interviewer_name"] = interview_data.get("interviewer_name")
        result["round_name"] = interview_data.get("round_name")
    return result
