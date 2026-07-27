from sqlalchemy import Text, cast, or_
from sqlalchemy.orm import Session

from app.modules.applications.application_response import extract_disqualified_by
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.reviews.review_model import Review
from app.modules.rounds.round_model import Round

RESUME_SHORTLISTING_ROUND_TYPE = "RESUME_SHORTLISTING"


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
) -> tuple[list[Candidate], int]:
    query = db.query(Candidate)

    if job_id:
        query = query.filter(Candidate.external_job_id == job_id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            Candidate.candidate_name.ilike(like) | Candidate.candidate_email.ilike(like)
        )
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
        _KEY_MAP = {"BUDGET": "CTC"}
        raw_reasons = [r.strip().upper() for r in reject_reason.split(",")]
        mapped_reasons = [_KEY_MAP.get(r, r) for r in raw_reasons]
        quoted_reasons = [f'"{r}"' for r in raw_reasons]
        query = query.filter(Candidate.reviews.isnot(None))
        query = query.filter(
            or_(
                *[Candidate.reviews[r].astext.isnot(None) for r in mapped_reasons],
                *[cast(Candidate.reviews["rejection_details"], Text).contains(q) for q in quoted_reasons],
            )
        )

    total = query.count()
    items = (
        query.order_by(Candidate.fit_score.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return items, total


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
) -> tuple[list[Candidate], int]:
    query = db.query(Candidate).filter(Candidate.final_verdict.isnot(None))
    if verdict:
        query = query.filter(Candidate.final_verdict == verdict)
    if job_id:
        query = query.filter(Candidate.external_job_id == job_id)
    total = query.count()
    items = query.order_by(Candidate.evaluated_at.desc().nullslast()).offset(offset).limit(limit).all()
    return items, total
