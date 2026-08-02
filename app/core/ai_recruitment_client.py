import uuid

import httpx

from app.core.config import settings
from app.core.secrets import get_secret
from app.core.service_token import create_service_token


class AiRecruitmentClient:
    def __init__(self) -> None:
        self.base_url = settings.RH_SERVICE_URL

    def _headers(self) -> dict[str, str]:
        rh_api_key = get_secret("RH_API_KEY")
        if rh_api_key:
            return {"Authorization": f"Bearer {rh_api_key}"}
        return {"Authorization": f"Bearer {create_service_token()}"}

    async def create_job(self, title: str, description: str, required_skills: list[str] | None = None, location: str | None = None, department: str | None = None, employment_type: str | None = None, external_job_id: str | None = None) -> dict | None:
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
                        "external_job_id": external_job_id,
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

    async def create_candidate_with_screening(
        self,
        external_job_id: str,
        name: str,
        email: str,
        phone: str | None = None,
        external_candidate_id: str | None = None,
        force: bool = False,
    ) -> dict | None:
        if not self.base_url:
            return None
        DUMMY_UUID = "00000000-0000-0000-0000-000000000000"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.base_url}/internal/talentos/jobs/{DUMMY_UUID}/candidates/with-screening",
                    json={
                        "name": name,
                        "email": email,
                        "phone": phone,
                        "external_job_id": external_job_id,
                        "external_candidate_id": external_candidate_id,
                        "force": force,
                    },
                    headers=self._headers(),
                )
                if resp.is_error:
                    return None
                return resp.json()
        except Exception:
            return None

    async def create_candidate_with_interview(
        self,
        external_job_id: str,
        name: str,
        email: str,
        phone: str | None = None,
        external_candidate_id: str | None = None,
        force: bool = False,
        interview_type: str | None = "AI_INTERVIEW",
    ) -> dict | None:
        if not self.base_url:
            return None
        DUMMY_UUID = "00000000-0000-0000-0000-000000000000"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.base_url}/internal/talentos/jobs/{DUMMY_UUID}/candidates/with-interview",
                    json={
                        "name": name,
                        "email": email,
                        "phone": phone,
                        "external_job_id": external_job_id,
                        "external_candidate_id": external_candidate_id,
                        "force": force,
                        "interview_type": interview_type,
                    },
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

    async def get_job_questions(self, job_id: str, external_job_id: str | None = None) -> dict | None:
        if not self.base_url:
            return None
        params = {"external_job_id": external_job_id} if external_job_id else None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/talentos/jobs/{job_id}/questions",
                    params=params,
                    headers=self._headers(),
                )
                if resp.is_error:
                    return None
                return resp.json()
        except Exception:
            return None

    async def update_job_questions(
        self,
        job_id: str,
        screening_questions: list | None = None,
        interview_questions: list | None = None,
        external_job_id: str | None = None,
    ) -> dict | None:
        if not self.base_url:
            return None
        payload: dict = {}
        if screening_questions is not None:
            payload["screening_questions"] = screening_questions
        if interview_questions is not None:
            payload["interview_questions"] = interview_questions
        params = {"external_job_id": external_job_id} if external_job_id else None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.put(
                    f"{self.base_url}/internal/talentos/jobs/{job_id}/questions",
                    params=params,
                    json=payload,
                    headers=self._headers(),
                )
                if resp.is_error:
                    return None
                return resp.json()
        except Exception:
            return None
