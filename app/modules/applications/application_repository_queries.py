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


def build_active_interview_map(db: Session, candidates: list[Candidate]) -> dict[int, dict]:
    """Batch-load active interview snapshots keyed by candidate.id (no N+1)."""
    from app.core.constants import InterviewStatus
    from app.modules.interviews.models.interview import Interview
    from app.modules.rounds.round_model import Round
    from app.modules.slots.slot_model import Slot
    from app.modules.users.user_model import User

    result: dict[int, dict] = {}
    candidate_ids = [c.id for c in candidates]
    if not candidate_ids:
        return result

    current_round_by_candidate = {
        c.id: c.current_round_id for c in candidates if c.current_round_id
    }
    active_statuses = (InterviewStatus.SCHEDULED.value, InterviewStatus.RESCHEDULED.value)

    rows = (
        db.query(
            Round.candidate_id,
            Round.id.label("round_id"),
            Round.name.label("round_name"),
            Interview.id.label("interview_id"),
            Interview.status.label("interview_status"),
            Interview.created_at.label("interview_created_at"),
            Slot.start_at,
            Slot.employee_id,
            User.id.label("interviewer_user_id"),
            User.name.label("interviewer_name"),
        )
        .join(Interview, Interview.round_id == Round.id)
        .outerjoin(Slot, Slot.id == Interview.slot_id)
        .outerjoin(User, User.id == Slot.employee_id)
        .filter(
            Round.candidate_id.in_(candidate_ids),
            Interview.status.in_(active_statuses),
        )
        .order_by(Interview.created_at.desc())
        .all()
    )

    # Prefer interview on current_round_id; else latest active for the candidate.
    best: dict[int, object] = {}
    for row in rows:
        cid = row.candidate_id
        if cid is None:
            continue
        preferred_round = current_round_by_candidate.get(cid)
        existing = best.get(cid)
        if existing is None:
            best[cid] = row
            continue
        if preferred_round and row.round_id == preferred_round and existing.round_id != preferred_round:
            best[cid] = row

    for cid, row in best.items():
        result[cid] = {
            "id": str(row.interview_id),
            "status": row.interview_status,
            "start_at": row.start_at.isoformat() if row.start_at else None,
            "round_id": str(row.round_id),
            "round_name": row.round_name,
            "interviewer_user_id": row.interviewer_user_id,
            "interviewer_name": row.interviewer_name,
        }
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
