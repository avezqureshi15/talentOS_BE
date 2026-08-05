from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.modules.applications.application_response import extract_disqualified_by
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.reviews.review_model import Review
from app.modules.rounds.round_model import Round

RESUME_SHORTLISTING_ROUND_TYPE = "RESUME_SHORTLISTING"

# Mirrors the FE pipeline stage tabs (STAGE_FILTER_MAP in detail.constants.ts).
# key -> (stage values, status values); "waiting-evaluation" uses OR semantics.
STAGE_QUERY_MAP: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "resume-shortlisting": (("RESUME_SHORTLISTING", "RESUME_SHORTLISTED"), ()),
    "screening": (("SCREENING", "AI_SCREENING"), ()),
    "interview": (
        ("INTERVIEW", "AI_INTERVIEW"),
        ("INTERVIEW_SCHEDULED", "INTERVIEW_RESCHEDULED", "INTERVIEW_CANCELLED"),
    ),
    "waiting-evaluation": (("WAITING_FOR_EVALUATION",), ("WAITING_FOR_REVIEW",)),
    "evaluated": (("INTERVIEW", "AI_INTERVIEW"), ("UNDER_EVALUATION",)),
}


def _apply_candidate_filters(
    db: Session,
    job_id: str | None = None,
    status: str | None = None,
    schedule: str | None = None,
    round_verdict: str | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    exclude_finalized: bool = False,
    search: str | None = None,
    reject_reason: str | None = None,
    stage: str | None = None,
    candidate_type: str | None = None,
    archived: bool | None = None,
):
    query = db.query(Candidate)

    if job_id:
        query = query.filter(Candidate.external_job_id == job_id)
    if archived is not None:
        query = query.filter(Candidate.archived == archived)
    if search:
        like = f"%{search}%"
        query = query.filter(
            Candidate.candidate_name.ilike(like) | Candidate.candidate_email.ilike(like)
        )
    if candidate_type:
        query = query.filter(Candidate.candidate_type.ilike(candidate_type.strip()))
    if status:
        query = query.filter(Candidate.status == status)
    if schedule == "scheduled":
        query = query.filter(Candidate.scheduled == True)
    elif schedule == "unscheduled":
        query = query.filter(Candidate.scheduled == False)
    if min_score is not None:
        query = query.filter(Candidate.fit_score >= min_score)
    if max_score is not None:
        query = query.filter(Candidate.fit_score <= max_score)
    if date_from:
        query = query.filter(Candidate.created_at >= date_from)
    if date_to:
        query = query.filter(Candidate.created_at <= date_to)
    if exclude_finalized:
        query = query.filter(Candidate.final_verdict.is_(None))
    if round_verdict:
        query = query.outerjoin(Round, Candidate.current_round_id == Round.id)
        query = query.filter(
            or_(
                Candidate.review_verdict == round_verdict,
                Round.round_verdict == round_verdict,
            )
        )

    if reject_reason:
        raw_reasons = [r.strip().upper() for r in reject_reason.split(",")]
        query = query.filter(Candidate.reviews.isnot(None))
        query = query.filter(
            or_(
                *[
                    Candidate.reviews["rejection_details"].contains([{r: {}}])
                    for r in raw_reasons
                ]
            )
        )

    if stage:
        stage_key = stage.strip().lower().replace(" ", "-")
        if stage_key == "waiting-evaluation":
            query = query.filter(
                or_(
                    Candidate.stage.in_(("WAITING_FOR_EVALUATION",)),
                    Candidate.status.in_(("WAITING_FOR_REVIEW",)),
                )
            )
        else:
            stage_values, status_values = STAGE_QUERY_MAP.get(stage_key, ((), ()))
            if stage_values and status_values:
                query = query.filter(
                    Candidate.stage.in_(stage_values),
                    Candidate.status.in_(status_values),
                )
            elif stage_values:
                query = query.filter(Candidate.stage.in_(stage_values))

    return query


def get_candidates_by_job_paginated(
    db: Session,
    job_id: str | None = None,
    status: str | None = None,
    schedule: str | None = None,
    round_verdict: str | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
    offset: int = 0,
    exclude_finalized: bool = False,
    search: str | None = None,
    reject_reason: str | None = None,
    stage: str | None = None,
    candidate_type: str | None = None,
    archived: bool | None = None,
) -> tuple[list[Candidate], int]:
    query = _apply_candidate_filters(
        db,
        job_id=job_id,
        status=status,
        schedule=schedule,
        round_verdict=round_verdict,
        min_score=min_score,
        max_score=max_score,
        date_from=date_from,
        date_to=date_to,
        exclude_finalized=exclude_finalized,
        search=search,
        reject_reason=reject_reason,
        stage=stage,
        candidate_type=candidate_type,
        archived=archived,
    )

    total = query.count()
    items = (
        query.order_by(Candidate.updated_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return items, total


def count_candidates_by_stage(
    db: Session,
    job_id: str | None = None,
    status: str | None = None,
    schedule: str | None = None,
    round_verdict: str | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    exclude_finalized: bool = False,
    search: str | None = None,
    reject_reason: str | None = None,
    stage: str | None = None,
    archived: bool | None = False,
    apply_reject_reason_override: bool = True,
) -> dict[str, int]:
    """Per-stage counts for the pipeline tabs, using the same filters as the list query.
    The disqualified-by (reject_reason) filter only applies to the resume-shortlisting
    tab, so it is excluded from the base counts and applied to that stage separately."""
    query = _apply_candidate_filters(
        db,
        job_id=job_id,
        status=status,
        schedule=schedule,
        round_verdict=round_verdict,
        min_score=min_score,
        max_score=max_score,
        date_from=date_from,
        date_to=date_to,
        exclude_finalized=exclude_finalized,
        search=search,
        archived=archived,
    )

    rows = (
        query.with_entities(Candidate.stage, Candidate.status, func.count(Candidate.id))
        .group_by(Candidate.stage, Candidate.status)
        .all()
    )

    counts: dict[str, int] = {key: 0 for key in STAGE_QUERY_MAP}
    for stage_value, status_value, cnt in rows:
        matched = False
        for key, (stage_values, status_values) in STAGE_QUERY_MAP.items():
            stage_match = stage_value in stage_values
            status_match = not status_values or status_value in status_values
            if stage_match and status_match:
                counts[key] += cnt
                matched = True
                break
        if not matched and (
            stage_value == "WAITING_FOR_EVALUATION" or status_value == "WAITING_FOR_REVIEW"
        ):
            counts["waiting-evaluation"] += cnt

    if reject_reason and apply_reject_reason_override:
        filtered_query = _apply_candidate_filters(
            db,
            job_id=job_id,
            status=status,
            schedule=schedule,
            round_verdict=round_verdict,
            min_score=min_score,
            max_score=max_score,
            date_from=date_from,
            date_to=date_to,
            exclude_finalized=exclude_finalized,
            search=search,
            reject_reason=reject_reason,
            stage="resume-shortlisting",
            archived=archived,
        )
        counts["resume-shortlisting"] = filtered_query.count()

    return counts


def build_review_map(db: Session, candidates: list[Candidate]) -> dict[str, Review]:
    review_map: dict[str, Review] = {}
    round_ids = [c.current_round_id for c in candidates if c.current_round_id]
    if round_ids:
        ai_reviews = (
            db.query(Review)
            .filter(
                Review.round_id.in_(round_ids),
                Review.entity_type == "AI",
            )
            .all()
        )
        for rv in ai_reviews:
            review_map[str(rv.round_id)] = rv
    return review_map


def build_disqualified_by_map(db: Session, candidates: list[Candidate]) -> dict[int, list[str]]:
    """Map candidate_id -> disqualification tags from resume-shortlisting AI reviews."""
    if not candidates:
        return {}

    candidate_ids = [c.id for c in candidates]
    result: dict[int, list[str]] = {cid: [] for cid in candidate_ids}

    resume_rounds = (
        db.query(Round)
        .filter(
            Round.candidate_id.in_(candidate_ids),
            Round.round_type == RESUME_SHORTLISTING_ROUND_TYPE,
        )
        .all()
    )
    if not resume_rounds:
        return result

    round_to_candidate = {r.id: r.candidate_id for r in resume_rounds if r.candidate_id is not None}
    ai_reviews = (
        db.query(Review)
        .filter(
            Review.round_id.in_(list(round_to_candidate.keys())),
            Review.entity_type == "AI",
        )
        .all()
    )
    for review in ai_reviews:
        candidate_id = round_to_candidate.get(review.round_id)
        if candidate_id is None:
            continue
        payload = review.reviews if isinstance(review.reviews, dict) else {}
        rejection_details = payload.get("rejection_details")
        tags = extract_disqualified_by(rejection_details if isinstance(rejection_details, list) else None)
        if tags:
            existing = result[candidate_id]
            for tag in tags:
                if tag not in existing:
                    existing.append(tag)

    return result


def get_finalized_candidates(
    db: Session,
    verdict: str | None = None,
    job_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    archived: bool = False,
) -> tuple[list[Candidate], int]:
    query = db.query(Candidate).filter(Candidate.final_verdict.isnot(None))
    if verdict:
        query = query.filter(Candidate.final_verdict == verdict)
    if job_id:
        query = query.filter(Candidate.external_job_id == job_id)
    if archived is not None:
        query = query.filter(Candidate.archived == archived)
    total = query.count()
    items = query.order_by(Candidate.updated_at.desc().nullslast()).offset(offset).limit(limit).all()
    return items, total
