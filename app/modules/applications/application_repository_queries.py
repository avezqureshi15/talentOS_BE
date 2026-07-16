from sqlalchemy import Text, cast, or_
from sqlalchemy.orm import Session

from app.modules.evaluations.evaluation_model import Candidate
from app.modules.reviews.review_model import Review
from app.modules.rounds.round_model import Round


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
        query = query.join(Round, Candidate.current_round_id == Round.id)
        query = query.filter(Round.round_verdict == round_verdict)

    if reject_reason:
        reasons = [f'"{r.strip().upper()}"' for r in reject_reason.split(",")]
        query = query.filter(Candidate.reviews.isnot(None))
        query = query.filter(
            or_(*[cast(Candidate.reviews["rejection_details"], Text).contains(r) for r in reasons])
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
