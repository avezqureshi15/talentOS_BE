"""One-off backfill: mirror AI interview status from ai-recruitment-poc into talentOS.

For a single hiring request, sync ``candidates.status`` for every candidate that is
currently in the ``AI_INTERVIEW`` stage, using each candidate's latest POC
interview session:

    pending / scheduled      -> INTERVIEW_SCHEDULED
    in_progress              -> ONGOING
    assessed / completed     -> UNDER_EVALUATION
    expired                  -> NO_SHOW

Only ``candidates.status`` is touched (stage stays ``AI_INTERVIEW``). Candidates
without any POC session are left unchanged. ``final_verdict``, other jobs and
other stages are never modified.

Usage:
    python scripts/backfill_interview_status.py --job-id <hiring_request_id> [--dry-run]
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2  # noqa: E402

from app.core.config import settings  # noqa: E402

POC_DATABASE_URL = os.getenv(
    "AI_RECRUITMENT_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/ai_recruitment",
)

SESSION_TO_STATUS = {
    "scheduled": "INTERVIEW_SCHEDULED",
    "pending": "INTERVIEW_SCHEDULED",
    "in_progress": "ONGOING",
    "ongoing": "ONGOING",
    "completed": "UNDER_EVALUATION",
    "assessed": "UNDER_EVALUATION",
    "assessment_failed": "UNDER_EVALUATION",
    "expired": "NO_SHOW",
    "cancelled": "NO_SHOW",
}


def load_hiring_request(db, job_id: str) -> dict | None:
    with db.cursor() as cur:
        cur.execute(
            """
            select id::text, external_job_id, rh_external_job_id, title
            from hiring_requests
            where id::text = %s
            """,
            (job_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "external_job_id": row[1],
        "rh_external_job_id": row[2],
        "title": row[3],
    }


def load_ai_interview_candidates(db, external_job_id: str) -> list[dict]:
    with db.cursor() as cur:
        cur.execute(
            """
            select id, candidate_name, status, rh_external_candidate_id
            from candidates
            where external_job_id::text = %s and stage = 'AI_INTERVIEW'
            order by id
            """,
            (external_job_id,),
        )
        return [
            {
                "id": row[0],
                "name": row[1],
                "status": row[2],
                "rh_external_candidate_id": row[3],
            }
            for row in cur.fetchall()
        ]


def load_latest_poc_sessions(db, poc_job_id: str) -> dict[str, dict]:
    with db.cursor() as cur:
        cur.execute(
            """
            with latest as (
              select distinct on (s.candidate_id)
                     s.candidate_id, s.id, s.status,
                     (select count(*) from interview_reports r
                      where r.interview_session_id = s.id) as has_report
              from interview_sessions s
              where s.job_id::text = %s
              order by s.candidate_id, s.created_at desc
            )
            select candidate_id::text, status, has_report from latest
            """,
            (poc_job_id,),
        )
        return {
            row[0]: {"status": row[1], "has_report": row[2]}
            for row in cur.fetchall()
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True, help="talentOS hiring_request id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    talentos_db = psycopg2.connect(settings.DATABASE_URL)
    try:
        hr = load_hiring_request(talentos_db, args.job_id)
        if not hr:
            print(f"ERROR: hiring request {args.job_id} not found")
            return
        if not hr["external_job_id"] or not hr["rh_external_job_id"]:
            print("ERROR: hiring request missing external_job_id / rh_external_job_id")
            return

        print(
            f"Job: {hr['title'] or hr['id']} | external_job_id={hr['external_job_id']} "
            f"| poc rh_external_job_id={hr['rh_external_job_id']}"
        )

        candidates = load_ai_interview_candidates(talentos_db, hr["external_job_id"])
        if not candidates:
            print("No candidates in AI_INTERVIEW stage for this job - nothing to do.")
            return

        poc_db = psycopg2.connect(POC_DATABASE_URL)
        try:
            poc = load_latest_poc_sessions(poc_db, hr["rh_external_job_id"])
        finally:
            poc_db.close()

        rows: list[dict] = []
        for cand in candidates:
            session = poc.get(cand["rh_external_candidate_id"] or "")
            if not session:
                rows.append({
                    "cand": cand, "current": cand["status"], "target": None,
                    "update": False, "source": "no session found",
                })
                continue
            target = SESSION_TO_STATUS.get(session["status"])
            rows.append({
                "cand": cand,
                "current": cand["status"],
                "target": target,
                "update": target is not None and target != cand["status"],
                "source": f"poc_status={session['status']}",
            })

        print(f"\n{'id':>3} | {'name':<10} | {'current':<22} | {'target':<22} | source")
        print("-" * 95)
        for row in rows:
            cand = row["cand"]
            target = row["target"] if row["target"] is not None else "skip"
            print(
                f"{cand['id']:>3} | {(cand['name'] or '?'):<10} | "
                f"{(cand['status'] or '-'):<22} | {target:<22} | {row['source']}"
            )

        updates = [r for r in rows if r["update"]]
        print(f"\nTotal AI_INTERVIEW candidates: {len(rows)} | to update: {len(updates)}")

        if args.dry_run:
            print("DRY-RUN: no changes written.")
            return

        with talentos_db.cursor() as cur:
            for row in updates:
                cur.execute(
                    "update candidates set status = %s where id = %s",
                    (row["target"], row["cand"]["id"]),
                )
                print(
                    f"Update candidate id={row['cand']['id']} {row['cand']['name']}: "
                    f"{row['cand']['status']} -> {row['target']}"
                )
        talentos_db.commit()
        print(f"Committed {len(updates)} status update(s).")
    finally:
        talentos_db.close()


if __name__ == "__main__":
    main()