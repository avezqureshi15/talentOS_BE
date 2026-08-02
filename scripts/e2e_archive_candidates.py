import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.modules.auth.auth_service import AuthService  # noqa: E402
from app.modules.evaluations.evaluation_model import Candidate  # noqa: E402
from app.modules.hiring_requests.hiring_request_model import HiringRequest  # noqa: E402
from app.modules.rounds.round_model import Round  # noqa: E402, F401
from app.modules.users.user_model import User  # noqa: E402

BASE = "http://127.0.0.1:8010/api/v1"
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

    hr = db.query(HiringRequest).filter(HiringRequest.external_job_id.isnot(None)).first()
    if not hr:
        print("SKIP: no hiring request with external_job_id")
        return
    external_job_id = str(hr.external_job_id)
    job_query_id = str(hr.id)

    cand = Candidate(
        external_application_id=f"E2E-ARCHIVE-{tag}",
        external_job_id=external_job_id,
        candidate_name=f"E2E Archive {tag}",
        candidate_email=f"e2e-archive-{tag}@tmp.test",
        status="RESUME_SHORTLISTED",
        stage="RESUME_SHORTLISTING",
        fit_score=80,
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    candidate_id = cand.id
    print(f"Seeded candidate_id={candidate_id} job={external_job_id}")

    u = User(
        emp_id=f"TMP-E2E-{tag}",
        email=f"e2e-archive-{tag}@tmp.test",
        name="E2E Archive Test",
        password_hash=None,
        auth_provider="google",
        tenant_id=None,
        is_active=True,
        status="active",
        user_type="employee",
        designation="QA",
        department="QA",
        role="recruiter",
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
        print("== initial: not archived ==")
        r = httpx.get(f"{BASE}/applications/?job_id={job_query_id}&archived=true", headers=headers, timeout=30)
        check("200 archived=true", r.status_code == 200, r.text)
        check("not in archived list", all(c["candidate_id"] != candidate_id for c in r.json()["data"]), r.text)
        r2 = httpx.get(f"{BASE}/applications/?job_id={job_query_id}", headers=headers, timeout=30)
        check("200 default list", r2.status_code == 200, r2.text)
        check("in default list", any(c["candidate_id"] == candidate_id for c in r2.json()["data"]), r2.text)

        print("== archive ==")
        r3 = httpx.patch(f"{BASE}/applications/{candidate_id}/archive", json={"archived": True}, headers=headers, timeout=30)
        check("200 archive", r3.status_code == 200, r3.text)
        check("archived=true response", r3.json().get("archived") is True, r3.text)

        r4 = httpx.get(f"{BASE}/applications/?job_id={job_query_id}", headers=headers, timeout=30)
        check("hidden from default list", all(c["candidate_id"] != candidate_id for c in r4.json()["data"]), r4.text)
        r5 = httpx.get(f"{BASE}/applications/?job_id={job_query_id}&archived=true", headers=headers, timeout=30)
        archived_item = next((c for c in r5.json()["data"] if c["candidate_id"] == candidate_id), None)
        check("present in archived list", archived_item is not None, r5.text)
        check("archived flag in payload", bool(archived_item and archived_item["archived"]), r5.text)

        print("== final-verdict + board exclusion ==")
        r6 = httpx.patch(f"{BASE}/applications/{candidate_id}/final-verdict", json={"verdict": "SELECTED"}, headers=headers, timeout=30)
        check("200 final-verdict", r6.status_code == 200, r6.text)
        r7 = httpx.get(f"{BASE}/applications/final-verdicts?job_id={job_query_id}", headers=headers, timeout=30)
        check("archived excluded from board", all(c["candidate_id"] != candidate_id for c in r7.json()["data"]), r7.text)
        r8 = httpx.get(f"{BASE}/applications/final-verdicts?job_id={job_query_id}&archived=true", headers=headers, timeout=30)
        check("archived present in board(archived=true)", any(c["candidate_id"] == candidate_id for c in r8.json()["data"]), r8.text)

        print("== restore ==")
        r9 = httpx.patch(f"{BASE}/applications/{candidate_id}/archive", json={"archived": False}, headers=headers, timeout=30)
        check("200 restore", r9.status_code == 200, r9.text)
        check("archived=false response", r9.json().get("archived") is False, r9.text)
        r10 = httpx.get(f"{BASE}/applications/?job_id={job_query_id}", headers=headers, timeout=30)
        check("back in default list", any(c["candidate_id"] == candidate_id for c in r10.json()["data"]), r10.text)
        r11 = httpx.get(f"{BASE}/applications/final-verdicts?job_id={job_query_id}", headers=headers, timeout=30)
        check("back on board", any(c["candidate_id"] == candidate_id for c in r11.json()["data"]), r11.text)

        print("== 404 unknown candidate ==")
        r12 = httpx.patch(f"{BASE}/applications/99999999/archive", json={"archived": True}, headers=headers, timeout=30)
        check("404 unknown", r12.status_code == 404, r12.text)

        print("== 403 no workflow permission ==")
        u2 = User(
            emp_id=f"TMP-E2E-RO-{tag}",
            email=f"e2e-ro-{tag}@tmp.test",
            name="E2E RO Test",
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
        db.add(u2)
        db.commit()
        db.refresh(u2)
        token2, _, _ = AuthService(db).create_tokens(u2.id)
        r13 = httpx.patch(f"{BASE}/applications/{candidate_id}/archive", json={"archived": True}, headers={"Authorization": f"Bearer {token2}"}, timeout=30)
        check("403 no workflow", r13.status_code == 403, r13.text)
    finally:
        db.query(Candidate).filter(Candidate.id == candidate_id).delete()
        db.query(User).filter(User.emp_id.like(f"TMP-E2E-%{tag}")).delete()
        db.commit()
        db.close()

    print(f"\nRESULT: PASS={PASS} FAIL={FAIL}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()

