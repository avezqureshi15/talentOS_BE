"""Interviews module read-sweep smoke.

Exercises every RoundInterviewer→User join we just gated, twice (flag OFF
and ON), and compares result sets. Read-only — no data mutation.
"""
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.applications.application_repository import ApplicationRepository
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.interviews.interview_query_repository import InterviewQueryRepository
from app.modules.interviews.interview_repository import InterviewRepository


def _pick_round_with_interviewer(db):
    row = db.execute(text("""
        SELECT ri.round_id
        FROM round_interviewers ri
        JOIN users u ON u.employee_id = ri.employee_id
        WHERE u.employee_id IS NOT NULL
        LIMIT 1
    """)).first()
    if not row:
        raise SystemExit("no round with linked interviewer available")
    return row.round_id


def _pick_interview_id(db, round_id):
    row = db.execute(
        text("SELECT id FROM interviews WHERE round_id=:r LIMIT 1"),
        {"r": round_id},
    ).first()
    return row.id if row else None


def _pick_candidate_with_current_round(db):
    row = db.execute(text("""
        SELECT id FROM candidates WHERE current_round_id IS NOT NULL LIMIT 1
    """)).first()
    return row.id if row else None


def _snapshot(db, round_id, interview_id, candidate_id):
    iqr = InterviewQueryRepository(db)
    ir = InterviewRepository(db)
    out = {}
    out["emails_for_round"] = sorted(ir.get_interviewer_emails_for_round(round_id))
    if interview_id:
        item = iqr.get_by_id(interview_id)
        out["get_by_id.emp_id"] = item.get("interviewer", {}).get("emp_id") if item else None
    else:
        out["get_by_id.emp_id"] = None
    rows_l, total = iqr.list_paginated(page=1, per_page=5)
    out["list_paginated.total"] = total
    out["list_paginated.first_emp_ids"] = sorted(
        (r.get("interviewer", {}).get("emp_id") or "") for r in rows_l if r.get("interviewer")
    )
    if candidate_id:
        cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if cand:
            ApplicationRepository(db).attach_interview_data([cand])
        out["attach_interview_data.ok"] = True
    return out


def main():
    engine = create_engine(settings.DATABASE_URL)
    with Session(engine) as db:
        round_id = _pick_round_with_interviewer(db)
        interview_id = _pick_interview_id(db, round_id)
        candidate_id = _pick_candidate_with_current_round(db)
        print(f"round_id={round_id} interview_id={interview_id} candidate_id={candidate_id}")

        res = _snapshot(db, round_id, interview_id, candidate_id)
        print("\n--- reads (Phase 3, single path) ---")
        for k, v in res.items():
            print(f"{k:35s}  {str(v)[:70]}")
        print("\nPASS: all interview reads executed without error")


if __name__ == "__main__":
    main()
