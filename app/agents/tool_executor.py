"""
Maps Claude tool calls → service layer functions.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.chat import ChatSession
from app.models.job_posting import JobPosting
from app.models.candidate import Candidate
from app.services.jd_service import JDService
from app.services.bench_service import BenchService
from app.services.job_service import JobService
from app.services.band_service import BandService
from app.schemas.job_posting import JobPostingCreate


class ToolExecutor:
    @staticmethod
    async def execute(
        tool_name: str,
        tool_input: dict,
        db: AsyncSession,
        hr_email: str,
        session: ChatSession,
    ) -> dict:

        if tool_name == "generate_jd":
            return await ToolExecutor._generate_jd(tool_input, db, hr_email, session)

        elif tool_name == "check_bench":
            return await ToolExecutor._check_bench(tool_input, db, hr_email)

        elif tool_name == "post_job":
            return await ToolExecutor._post_job(tool_input, db, hr_email)

        elif tool_name == "get_job_status":
            return await ToolExecutor._get_job_status(tool_input, db)

        elif tool_name == "get_shortlisted_candidates":
            return await ToolExecutor._get_shortlisted(tool_input, db)

        return {"error": f"Unknown tool: {tool_name}"}

    @staticmethod
    async def _generate_jd(input: dict, db: AsyncSession, hr_email: str, session: ChatSession) -> dict:
        # Resolve designation from band lookup
        designation = await BandService.get_designation(db, input["stream"], input["band"])
        if not designation:
            designation = f"{input['stream']} {input['band']}"

        # Generate JD text
        jd_text = await JDService.generate(
            stream=input["stream"],
            band=input["band"],
            designation=designation,
            experience_min=input["experience_min"],
            skills_required=input["skills_required"],
            urgency=input["urgency"],
            employment_type=input["employment_type"],
            role_expectations=input.get("role_expectations", ""),
        )

        # Create draft job posting
        job_data = JobPostingCreate(
            title=designation,
            stream=input["stream"],
            band=input["band"],
            designation=designation,
            employment_type=input["employment_type"],
            experience_min=input["experience_min"],
            skills_required=input["skills_required"],
            urgency=input["urgency"],
            jd_text=jd_text,
            jd_raw={
                "stream": input["stream"],
                "band": input["band"],
                "experience_min": input["experience_min"],
                "skills_required": input["skills_required"],
            },
            ats_threshold=input.get("ats_threshold", 70),
        )

        job = await JobService.create(db, job_data, actor_email=hr_email)

        # Link session to job
        session.job_posting_id = job.id
        await db.flush()

        return {
            "job_posting_id": str(job.id),
            "designation": designation,
            "jd_text": jd_text,
            "ats_threshold": job.ats_threshold,
            "message": "JD generated and saved as draft. Please review and confirm to post.",
        }

    @staticmethod
    async def _check_bench(input: dict, db: AsyncSession, hr_email: str) -> dict:
        employees = await BenchService.check_bench(input["stream"], input["band"])

        if not employees:
            return {
                "found": False,
                "count": 0,
                "message": f"No bench candidates found for {input['stream']} {input['band']}.",
            }

        return {
            "found": True,
            "count": len(employees),
            "employees": employees,
            "message": f"Found {len(employees)} available employee(s) on bench.",
        }

    @staticmethod
    async def _post_job(input: dict, db: AsyncSession, hr_email: str) -> dict:
        from uuid import UUID
        try:
            job_id = UUID(input["job_posting_id"])
        except ValueError:
            return {"error": "Invalid job posting ID"}

        job = await JobService.get_or_404(db, job_id)
        published = await JobService.publish(db, job, actor_email=hr_email)

        return {
            "success": True,
            "job_posting_id": str(published.id),
            "title": published.title,
            "careers_page_id": published.careers_page_id,
            "message": f"{published.title} is now live on the careers page.",
        }

    @staticmethod
    async def _get_job_status(input: dict, db: AsyncSession) -> dict:
        from uuid import UUID
        result = await db.execute(
            select(JobPosting).where(JobPosting.id == UUID(input["job_posting_id"]))
        )
        job = result.scalar_one_or_none()
        if not job:
            return {"error": "Job not found"}

        return {
            "job_posting_id": str(job.id),
            "title": job.title,
            "status": job.status,
            "total_applications": job.total_applications,
            "total_shortlisted": job.total_shortlisted,
            "ats_threshold": job.ats_threshold,
        }

    @staticmethod
    async def _get_shortlisted(input: dict, db: AsyncSession) -> dict:
        from uuid import UUID
        result = await db.execute(
            select(Candidate).where(
                Candidate.job_posting_id == UUID(input["job_posting_id"]),
                Candidate.is_shortlisted == True,
            ).order_by(Candidate.fit_score.desc())
        )
        candidates = result.scalars().all()

        return {
            "count": len(candidates),
            "candidates": [
                {
                    "name": c.name,
                    "email": c.email,
                    "fit_score": float(c.fit_score or 0),
                    "status": c.status,
                }
                for c in candidates
            ],
        }
