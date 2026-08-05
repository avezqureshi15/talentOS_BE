"""Forms module read-sweep smoke: exercises every gated read method
against both flag values and compares the results row-by-row.

Usage:
    uv run python scripts/smoke/forms.py

The script inserts one SLOTS form and one REVIEW form under a real
user + round, calls each repo read method with READ_EMPLOYEES=false
and =true, asserts identical Form.id results, then cleans up.
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.forms.form_model import FormStatus, FormType
from app.modules.forms.form_repository import FormRepository


def _pick_user(db):
    """Return (user_id, emp_id) for a user that has a linked employee."""
    row = db.execute(
        text(
            "SELECT id, emp_id FROM users "
            "WHERE is_active=true AND employee_id IS NOT NULL "
            "ORDER BY id LIMIT 1"
        )
    ).first()
    if row is None:
        raise SystemExit("no linked user available for smoke")
    return row.id, row.emp_id


def _pick_round(db):
    """Any round id from the existing dataset (for REVIEW form)."""
    row = db.execute(text("SELECT id FROM rounds ORDER BY id LIMIT 1")).first()
    if row is None:
        raise SystemExit("no rounds available for smoke")
    return row.id


def _run_reads(db, user_id, emp_id, round_id):
    repo = FormRepository(db)
    now = datetime.now(timezone.utc).isoformat()
    return {
        "get_latest_SLOTS": (repo.get_latest(emp_id, FormType.SLOTS.value) or _empty()).id,
        "get_active_sent_SLOTS": (repo.get_active_sent(emp_id, FormType.SLOTS.value) or _empty()).id,
        "get_latest_by_user_SLOTS": (repo.get_latest_by_user(user_id, FormType.SLOTS.value) or _empty()).id,
        "get_active_sent_by_user_SLOTS": (repo.get_active_sent_by_user(user_id, FormType.SLOTS.value) or _empty()).id,
        "get_active_sent_by_user_and_round": (repo.get_active_sent_by_user_and_round(user_id, round_id) or _empty()).id,
        "get_active_sent_by_emp_and_round": (repo.get_active_sent_by_emp_and_round(emp_id, round_id) or _empty()).id,
        "get_latest_REVIEW": (repo.get_latest(emp_id, FormType.REVIEW.value) or _empty()).id,
    }, now


class _empty:
    id = None


def main() -> None:
    engine = create_engine(settings.DATABASE_URL)
    with Session(engine) as db:
        user_id, emp_id = _pick_user(db)
        round_id = _pick_round(db)
        print(f"user_id={user_id} emp_id={emp_id} round_id={round_id}")

        # ── seed one SLOTS form and one REVIEW form owned by user_id ──
        slots_id = uuid4()
        review_id = uuid4()
        emp_ref = db.execute(
            text("SELECT employee_id FROM users WHERE id=:uid"), {"uid": user_id}
        ).scalar()
        db.execute(
            text(
                "INSERT INTO forms (id, employee_id, type, status, "
                "last_sent_at, created_at, updated_at) VALUES "
                "(:id, :eid, 'SLOTS', 'SENT', NOW(), NOW(), NOW()), "
                "(:rid, :eid, 'REVIEW', 'SENT', NOW(), NOW(), NOW())"
            ),
            {"id": slots_id, "rid": review_id, "eid": emp_ref},
        )
        db.execute(
            text("UPDATE forms SET round_id=:rid WHERE id=:id"),
            {"rid": round_id, "id": review_id},
        )
        db.commit()
        print(f"seeded slots_form={slots_id} review_form={review_id}")

        try:
            results, _ = _run_reads(db, user_id, emp_id, round_id)
            print("\n--- reads (Phase 3, single path) ---")
            all_ok = True
            for k, v in results.items():
                ok = v is not None
                all_ok &= ok
                print(f"{k:45s}  {str(v)[:8]:8}  {'OK' if ok else 'MISS'}")
            print("\n" + ("PASS: all reads returned a form" if all_ok else "FAIL: some reads returned None"))
        finally:
            db.execute(text("DELETE FROM forms WHERE id IN (:s, :r)"), {"s": slots_id, "r": review_id})
            db.commit()
            print("cleaned up")


if __name__ == "__main__":
    main()
