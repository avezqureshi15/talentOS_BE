import uuid

import httpx

from app.core.config import settings
from app.core.service_token import create_service_token


class AiRecruitmentClient:
    def __init__(self) -> None:
        self.base_url = settings.RH_SERVICE_URL

    def _headers(self) -> dict[str, str]:
        if settings.RH_API_KEY:
            return {"Authorization": f"Bearer {settings.RH_API_KEY}"}
        return {"Authorization": f"Bearer {create_service_token()}"}

    async def create_job(self, title: str, description: str, required_skills: list[str] | None = None, location: str | None = None, department: str | None = None, employment_type: str | None = None) -> dict | None:
        if not self.base_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/internal/talentos/jobs",
                    json={
                        "title": title,
                        "description": description,
                        "required_skills": required_skills,
                        "location": location,
                        "department": department,
                        "employment_type": employment_type,
                    },
                    headers=self._headers(),
                )
                if resp.is_error:
                    return None
                return resp.json()
        except Exception:
            return None

    async def create_candidate(self, job_id: str, name: str, email: str, phone: str | None = None, resume_url: str | None = None) -> dict | None:
        if not self.base_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/internal/talentos/jobs/{job_id}/candidates",
                    json={"name": name, "email": email, "phone": phone, "resume_url": resume_url},
                    headers=self._headers(),
                )
                if resp.is_error:
                    return None
                return resp.json()
        except Exception:
            return None

    async def trigger_screening(self, job_id: str, candidate_id: str) -> dict | None:
        if not self.base_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/internal/talentos/jobs/{job_id}/candidates/{candidate_id}/trigger-screening",
                    headers=self._headers(),
                )
                if resp.is_error:
                    return None
                return resp.json()
        except Exception:
            return None

    async def get_screening_result(self, job_id: str, candidate_id: str) -> dict | None:
        if not self.base_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/talentos/jobs/{job_id}/candidates/{candidate_id}/screening",
                    headers=self._headers(),
                )
                if resp.is_error:
                    return None
                return resp.json()
        except Exception:
            return None

    async def trigger_interview(self, job_id: str, candidate_id: str, interview_type: str | None = None) -> dict | None:
        if not self.base_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/internal/talentos/jobs/{job_id}/candidates/{candidate_id}/trigger-interview",
                    json={"interview_type": interview_type},
                    headers=self._headers(),
                )
                if resp.is_error:
                    return None
                return resp.json()
        except Exception:
            return None

    async def list_interviews(self, job_id: str, candidate_id: str) -> list | None:
        if not self.base_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/talentos/jobs/{job_id}/candidates/{candidate_id}/interviews",
                    headers=self._headers(),
                )
                if resp.is_error:
                    return None
                return resp.json()
        except Exception:
            return None

    async def get_interview_detail(self, job_id: str, candidate_id: str, interview_id: str) -> dict | None:
        if not self.base_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/talentos/jobs/{job_id}/candidates/{candidate_id}/interviews/{interview_id}",
                    headers=self._headers(),
                )
                if resp.is_error:
                    return None
                return resp.json()
        except Exception:
            return None

    async def list_candidates(self, job_id: str) -> list | None:
        if not self.base_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/talentos/jobs/{job_id}/candidates",
                    headers=self._headers(),
                )
                if resp.is_error:
                    return None
                return resp.json()
        except Exception:
            return None
