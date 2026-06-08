"""
Celery worker — resume evaluation task.
Triggered as soon as a candidate applies.
Flow: fetch resume → extract text → Claude parse → score → store if shortlisted
"""
import asyncio
from datetime import datetime, timezone
from uuid import UUID

from app.workers.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.services.eval_service import EvalService
from app.services.audit_service import AuditService


@celery_app.task(name="process_resume", bind=True, max_retries=3)
def process_resume_task(self, candidate_id: str):
    """
    Synchronous Celery entry point.
    Runs the async evaluation in an event loop.
    """
    try:
        asyncio.run(_evaluate_candidate(candidate_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


async def _evaluate_candidate(candidate_id_str: str):
    from sqlalchemy import select
    from app.models.candidate import Candidate
    from app.models.job_posting import JobPosting

    candidate_id = UUID(candidate_id_str)

    async with AsyncSessionLocal() as db:
        # Fetch candidate
        result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
        candidate = result.scalar_one_or_none()
        if not candidate:
            return

        # Fetch job posting for JD requirements
        job_result = await db.execute(
            select(JobPosting).where(JobPosting.id == candidate.job_posting_id)
        )
        job = job_result.scalar_one_or_none()
        if not job:
            return

        try:
            # Step 1: Extract text from resume PDF
            resume_text = await EvalService.extract_text_from_url(candidate.resume_url)

            if not resume_text.strip():
                candidate.status = "rejected"
                await db.commit()
                return

            # Step 2: Claude parses resume → structured profile
            parsed = await EvalService.parse_resume(resume_text)

            # Step 3: Deterministic scoring
            scoring = EvalService.compute_score(
                parsed_profile=parsed,
                jd_raw=job.jd_raw or {},
            )

            fit_score = scoring["fit_score"]

            # Step 4: Threshold check
            if fit_score >= job.ats_threshold:
                candidate.status = "shortlisted"
                candidate.is_shortlisted = True
                candidate.shortlisted_by = "system"
                candidate.shortlisted_at = datetime.now(timezone.utc)
                job.total_shortlisted += 1

                await AuditService.log(
                    db=db,
                    entity_type="candidate",
                    entity_id=candidate.id,
                    event_type="CANDIDATE_SHORTLISTED",
                    actor_email="system",
                    payload={
                        "name": candidate.name,
                        "fit_score": fit_score,
                        "shortlisted_by": "system",
                        "threshold": job.ats_threshold,
                    },
                )
            else:
                candidate.status = "rejected"

                await AuditService.log(
                    db=db,
                    entity_type="candidate",
                    entity_id=candidate.id,
                    event_type="CANDIDATE_REJECTED",
                    actor_email="system",
                    payload={
                        "name": candidate.name,
                        "fit_score": fit_score,
                        "threshold": job.ats_threshold,
                    },
                )

            # Store results regardless of shortlist outcome
            candidate.fit_score = fit_score
            candidate.score_breakdown = scoring["score_breakdown"]
            candidate.score_explanation = scoring["score_explanation"]
            candidate.evaluated_at = datetime.now(timezone.utc)

            await db.commit()

        except Exception as e:
            candidate.status = "rejected"
            await db.commit()
            raise e
