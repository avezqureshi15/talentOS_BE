"""
Careers Page integration — Supabase (existing app).
Writes job postings to the careers page Supabase project.
Schema will be confirmed once careers page schema is shared.
"""
from app.core.config import settings

# Lazy init so missing creds don't crash startup
_supabase_client = None


def get_supabase():
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    return _supabase_client


class CareersService:
    @staticmethod
    async def publish_job(job) -> str:
        """
        Write job posting to careers page Supabase.
        Returns the careers page record ID.
        TODO: update table/column names once careers page schema is confirmed.
        """
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            # Stub: careers page not configured yet
            return f"stub_{str(job.id)[:8]}"

        client = get_supabase()
        payload = {
            "title": job.title,
            "description": job.jd_text,
            "stream": job.stream,
            "band": job.band,
            "designation": job.designation,
            "employment_type": job.employment_type,
            "experience_min": job.experience_min,
            "status": "active",
            "talentos_job_id": str(job.id),
        }
        # TODO: replace "job_postings" with actual careers page table name
        response = client.table("job_postings").insert(payload).execute()
        return response.data[0]["id"]

    @staticmethod
    async def unpublish_job(careers_page_id: str):
        """Mark job as closed on careers page."""
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            return

        client = get_supabase()
        client.table("job_postings").update({"status": "closed"}).eq(
            "id", careers_page_id
        ).execute()
