import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402

from app.common.exceptions.notification_exception import NotificationNotFoundException  # noqa: E402
from app.db.session import engine, SessionLocal  # noqa: E402
from app.modules.tenants.tenant_model import Tenant  # noqa: E402, F401
from app.modules.forms.form_model import Form  # noqa: E402, F401
from app.modules.notifications.notification_model import Notification, NotificationType  # noqa: E402
from app.modules.notifications.notification_service import NotificationService  # noqa: E402
from app.modules.users.user_model import User  # noqa: E402

PASS = 0
FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"FAIL  {label}")


def make_user(db, tag):
    u = User(
        emp_id=f"TMP-{tag}-{uuid4().hex[:8]}",
        email=f"notif-{tag}-{uuid4().hex[:8]}@tmp.test",
        name=f"Notif Test {tag}",
        password_hash=None,
        auth_provider="google",
        tenant_id=None,
        is_active=True,
        status="active",
        user_type="employee",
        designation="QA",
        department="QA",
        role="employee",
        work_mode="office",
        delivery_status="yes",
        work_location_type="office",
        doj=date.today() - timedelta(days=30),
        date_of_birth=date(1995, 1, 1),
        band="B1",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def cleanup(db, users):
    for u in users:
        db.query(Notification).filter(Notification.employee_id == u.id).delete()
        db.query(User).filter(User.id == u.id).delete()
    db.commit()


def main():
    db: Session = SessionLocal()
    users = [make_user(db, "a"), make_user(db, "b")]
    u1, u2 = users
    svc = NotificationService(db=db)
    tag = uuid4().hex[:8]

    print("== strict type validation ==")
    try:
        svc.notify(employee_id=u1.id, notification_type="BOGUS", title="x")
        check("unknown type rejected", False)
    except ValueError:
        check("unknown type rejected", True)
    check("known type normalized", svc.validate_type("evaluation_completed") == "EVALUATION_COMPLETED")

    print("== create + unread_count sync ==")
    n1 = svc.notify(
        employee_id=u1.id,
        notification_type=NotificationType.EVALUATION_COMPLETED.value,
        title="Evaluation done",
        body="body",
        action_url="/hiring-requests/1",
        action_label="View candidate",
        dedupe_key=f"EVAL-{tag}",
    )
    db.commit()
    check("created", n1 is not None)
    check("unread incremented", svc.get_unread_count(u1.id) == 1)
    check("is_read false", n1.is_read is False)

    print("== dedupe (service + DB) ==")
    n1b = svc.notify(
        employee_id=u1.id,
        notification_type=NotificationType.EVALUATION_COMPLETED.value,
        title="dup",
        dedupe_key=f"EVAL-{tag}",
    )
    db.commit()
    check("service dedupe returns None", n1b is None)
    check("only one row", svc.get_unread_count(u1.id) == 1)

    print("== fan-out ==")
    created = svc.notify_many(
        [u1.id, u2.id, u1.id],
        notification_type=NotificationType.INTERVIEW_SCHEDULED.value,
        title="Interview",
        dedupe_key=f"IV-{tag}",
    )
    db.commit()
    check("fan-out created 2 (deduped)", created == 2)
    check("u1 unread=2, u2 unread=1", svc.get_unread_count(u1.id) == 2 and svc.get_unread_count(u2.id) == 1)

    print("== list_mine scoping ==")
    r1 = svc.list_mine(u1.id)
    check("u1 sees 2", r1.data.pagination.total_records == 2)
    r2 = svc.list_mine(u2.id)
    check("u2 sees 1", r2.data.pagination.total_records == 1)
    check("u2 only own", all(n.employee_id == u2.id for n in r2.data.notifications))
    check("sorted desc", r1.data.notifications[0].created_at >= r1.data.notifications[-1].created_at)
    check("type filter", svc.list_mine(u1.id, notification_type="EVALUATION_COMPLETED").data.pagination.total_records == 1)
    check("read filter", svc.list_mine(u1.id, is_read=False).data.pagination.total_records == 2)
    check("pagination", svc.list_mine(u1.id, per_page=1).data.pagination.has_more is True)

    print("== mark_read ownership ==")
    try:
        svc.mark_read(n1.id, u2.id)
        check("other user cannot mark", False)
    except NotificationNotFoundException:
        check("other user cannot mark", True)
    _ = svc.mark_read(n1.id, u1.id)
    check("owner can mark", n1.is_read is True and n1.read_at is not None)
    check("unread decremented", svc.get_unread_count(u1.id) == 1)
    check("idempotent re-mark keeps count", svc.get_unread_count(u1.id) == 1)

    print("== mark_all_read ==")
    updated = svc.mark_all_read(u1.id)
    check("marked all", updated == 1)
    check("unread 0", svc.get_unread_count(u1.id) == 0)
    check("filtered mark-all", svc.mark_all_read(u1.id, notification_type="JOB_ASSIGNED") == 0)

    print("== unread floor at 0 ==")
    svc.repository.decrement_unread(u1.id, amount=5)
    db.commit()
    check("floor 0", svc.get_unread_count(u1.id) == 0)

    cleanup(db, users)
    db.close()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
