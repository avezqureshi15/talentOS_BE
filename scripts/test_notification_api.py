import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.modules.auth.auth_service import AuthService  # noqa: E402
from app.modules.notifications.notification_model import Notification  # noqa: E402
from app.modules.tenants.tenant_model import Tenant  # noqa: E402, F401
from app.modules.forms.form_model import Form  # noqa: E402, F401
from app.modules.users.user_model import User  # noqa: E402

BASE = "http://127.0.0.1:8001/api/v1"
PASS = 0
FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"FAIL  {label}  {extra}")


def main():
    db = SessionLocal()
    tag = uuid4().hex[:8]
    u = User(
        emp_id=f"TMP-API-{tag}",
        email=f"notif-api-{tag}@tmp.test",
        name="Notif API Test",
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

    token, _, _ = AuthService(db).create_tokens(u.id)
    headers = {"Authorization": f"Bearer {token}"}

    try:
        print("== unread-count (empty) ==")
        r = httpx.get(f"{BASE}/notifications/unread-count", headers=headers, timeout=30)
        check("200", r.status_code == 200, r.text)
        check("count 0", r.json()["data"]["unread_count"] == 0, r.text)

        print("== create via admin: none, seed directly ==")
        from app.modules.notifications.notification_service import NotificationService
        svc = NotificationService(db=db)
        for i in range(3):
            svc.notify(
                employee_id=u.id,
                notification_type="EVALUATION_COMPLETED" if i % 2 == 0 else "INTERVIEW_SCHEDULED",
                title=f"Seed {i}",
                body="body",
                dedupe_key=f"API-{tag}-{i}",
            )
        db.commit()

        print("== list ==")
        r = httpx.get(f"{BASE}/notifications/", headers=headers, timeout=10)
        check("200", r.status_code == 200, r.text)
        data = r.json()["data"]
        check("3 rows", data["pagination"]["total_records"] == 3, r.text)
        check("has_more false", data["pagination"]["has_more"] is False)
        check("action fields present", "action_url" in data["notifications"][0] and "title" in data["notifications"][0])

        print("== unread-count = 3 ==")
        r = httpx.get(f"{BASE}/notifications/unread-count", headers=headers, timeout=30)
        check("count 3", r.json()["data"]["unread_count"] == 3, r.text)

        print("== type filter ==")
        r = httpx.get(f"{BASE}/notifications/?type=INTERVIEW_SCHEDULED", headers=headers, timeout=10)
        check("1 interview row", r.json()["data"]["pagination"]["total_records"] == 1, r.text)

        print("== pagination ==")
        r = httpx.get(f"{BASE}/notifications/?per_page=2", headers=headers, timeout=10)
        check("2 rows page1", len(r.json()["data"]["notifications"]) == 2, r.text)
        check("has_more true", r.json()["data"]["pagination"]["has_more"] is True, r.text)

        print("== invalid type rejected ==")
        r = httpx.get(f"{BASE}/notifications/?type=BOGUS", headers=headers, timeout=10)
        check("422", r.status_code == 422, r.text)

        print("== mark one read ==")
        first_id = data["notifications"][0]["id"]
        r = httpx.patch(f"{BASE}/notifications/{first_id}/read", headers=headers, timeout=10)
        check("200", r.status_code == 200, r.text)
        check("is_read true", r.json()["is_read"] is True, r.text)
        r = httpx.get(f"{BASE}/notifications/unread-count", headers=headers, timeout=30)
        check("count 2", r.json()["data"]["unread_count"] == 2, r.text)

        print("== ownership: other user 404 ==")
        other = User(
            emp_id=f"TMP-API2-{tag}", email=f"notif-api2-{tag}@tmp.test", name="Other",
            password_hash=None, auth_provider="google", tenant_id=None, is_active=True,
            status="active", user_type="employee", designation="QA", department="QA",
            role="employee", work_mode="office", delivery_status="yes", work_location_type="office",
            doj=date.today() - timedelta(days=30), date_of_birth=date(1995, 1, 1), band="B1",
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        token2, _, _ = AuthService(db).create_tokens(other.id)
        r = httpx.patch(f"{BASE}/notifications/{first_id}/read", headers={"Authorization": f"Bearer {token2}"}, timeout=10)
        check("404", r.status_code == 404, r.text)
        db.delete(other)
        db.commit()

        print("== mark-all read ==")
        r = httpx.patch(f"{BASE}/notifications/read-all", headers=headers, timeout=10)
        check("200", r.status_code == 200, r.text)
        check("updated 2", r.json()["data"]["updated"] == 2, r.text)
        r = httpx.get(f"{BASE}/notifications/unread-count", headers=headers, timeout=30)
        check("count 0", r.json()["data"]["unread_count"] == 0, r.text)

        print("== unauthenticated (missing header) 422 by app convention ==")
        r = httpx.get(f"{BASE}/notifications/", timeout=30)
        check("422", r.status_code == 422, r.text)
    finally:
        db.query(Notification).filter(Notification.employee_id == u.id).delete()
        db.delete(u)
        db.commit()
        db.close()

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
