"""Backfill contextual titles for notifications that were created with generic
producer text (e.g. "Review pending" / "Slot availability request").

Only touches notifications that still carry the old generic strings, resolving
context from the linked form -> candidate -> round -> hiring request.

Usage:
    python scripts/backfill_notification_titles.py [--dry-run]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.modules.evaluations.evaluation_model import Candidate  # noqa: E402
from app.modules.forms.form_model import Form, FormType  # noqa: E402
from app.modules.hiring_requests.hiring_request_model import HiringRequest  # noqa: E402
from app.modules.notifications.notification_model import Notification  # noqa: E402
from app.modules.rounds.round_model import Round  # noqa: E402

OLD_TITLES = {"Review pending", "Slot availability request"}


def resolve_context(db: Session, form_id) -> tuple[str, str, int | None]:
    form = db.query(Form).filter(Form.id == form_id).first()
    if not form:
        return "", "", None

    candidate_name = None
    job_title = None
    round_name = None
    hr = None
    if form.candidate_id:
        candidate = db.query(Candidate).filter(Candidate.id == form.candidate_id).first()
        candidate_name = candidate.candidate_name if candidate else None
    if form.round_id:
        round_obj = db.query(Round).filter(Round.id == form.round_id).first()
        if round_obj:
            round_name = round_obj.name
            if round_obj.jd_id:
                hr = db.query(HiringRequest).filter(HiringRequest.id == round_obj.jd_id).first()
                job_title = hr.title if hr else None

    if form.type == FormType.REVIEW.value:
        title = f"Review required for {candidate_name}" if candidate_name else "Review pending"
        parts = [part for part in (job_title, f"Round: {round_name}" if round_name else None) if part]
        body = " · ".join(parts) or "A form is waiting for your action."
    else:
        title = "Slot availability request"
        body = f"Your availability is needed to schedule interviews for {job_title}." if job_title else "A form is waiting for your action."

    return title, body, (hr.id if hr else None)


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    db: Session = SessionLocal()
    try:
        rows = (
            db.query(Notification)
            .filter(Notification.title.in_(OLD_TITLES), Notification.form_id.isnot(None))
            .all()
        )
        print(f"Found {len(rows)} notification(s) with generic titles")

        updated = 0
        for n in rows:
            title, body, job_id = resolve_context(db, n.form_id)
            if not title or title == n.title:
                continue
            print(
                f"  {n.id} {n.type}: {n.title!r} -> {title!r}"
                + (f" (job_id={job_id})" if job_id else "")
            )
            if not dry_run:
                n.title = title
                n.body = body
                if job_id and not n.job_id:
                    n.job_id = job_id
                updated += 1

        if not dry_run:
            db.commit()
            print(f"Committed {updated} update(s)")
        else:
            print(f"Dry run — would update {updated} (no changes written)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
