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


def extract_disqualified_by(rejection_details: list | None) -> list[str]:
    if not rejection_details:
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for item in rejection_details:
        if not isinstance(item, dict):
            continue
        criterion = item.get("criterion")
        if isinstance(criterion, str) and criterion.strip():
            tag = criterion.strip().upper()
        else:
            keys = [k for k in item.keys() if k not in ("JD", "Candidate", "criterion")]
            if not keys:
                continue
            tag = str(keys[0]).strip().upper()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def build_candidate_response(
    candidate: Candidate,
    hide_cover_letter: bool = False,
    events: list[dict] | None = None,
    disqualified_by: list[str] | None = None,
    interview_data: dict | None = None,
) -> dict:
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
        "disqualified_by": disqualified_by or [],
        "events": events,
        "interview_id": None,
        "interviewer_emp_id": None,
        "interviewer_name": None,
        "round_name": None,
        "scheduled_at": None,
        "scheduled_end_at": None,
    }
    if interview_data:
        result["interview_id"] = interview_data.get("interview_id")
        result["interviewer_emp_id"] = interview_data.get("interviewer_emp_id")
        result["interviewer_name"] = interview_data.get("interviewer_name")
        result["round_name"] = interview_data.get("round_name")
        result["scheduled_at"] = interview_data.get("scheduled_at")
        result["scheduled_end_at"] = interview_data.get("scheduled_end_at")
    return result
