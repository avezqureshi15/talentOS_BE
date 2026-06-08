"""
Resume evaluation service.
Step 1: Claude parses resume PDF → structured profile
Step 2: Deterministic scoring against JD requirements
"""
import json
import httpx
import anthropic
from pypdf import PdfReader
from io import BytesIO

from app.core.config import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


class EvalService:
    @staticmethod
    async def extract_text_from_url(resume_url: str) -> str:
        """Download PDF from URL and extract text."""
        async with httpx.AsyncClient() as http:
            response = await http.get(resume_url, timeout=30)
            response.raise_for_status()

        pdf = PdfReader(BytesIO(response.content))
        text = ""
        for page in pdf.pages:
            text += page.extract_text() or ""
        return text.strip()

    @staticmethod
    async def parse_resume(resume_text: str) -> dict:
        """
        Claude extracts structured data from raw resume text.
        Returns structured JSON profile.
        """
        prompt = f"""Extract structured information from this resume.
Return ONLY valid JSON with this exact structure:
{{
  "skills": ["skill1", "skill2"],
  "exp_years": <number>,
  "education": "<highest degree and field>",
  "companies": ["company1", "company2"],
  "current_role": "<most recent job title>",
  "role_history": ["role1 at company1", "role2 at company2"]
}}

Resume:
{resume_text[:4000]}
"""
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        # Strip markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"skills": [], "exp_years": 0, "education": "", "companies": [], "role_history": []}

    @staticmethod
    def compute_score(parsed_profile: dict, jd_raw: dict) -> dict:
        """
        Deterministic scoring. No LLM needed here.
        weights: skills 40%, experience 35%, qualifications 25%
        """
        required_skills = [
            s["skill"].lower()
            for s in (jd_raw.get("skills_required") or [])
            if s.get("priority") == "required"
        ]
        preferred_skills = [
            s["skill"].lower()
            for s in (jd_raw.get("skills_required") or [])
            if s.get("priority") == "preferred"
        ]
        candidate_skills = [s.lower() for s in (parsed_profile.get("skills") or [])]

        # Skills match (40%)
        if required_skills:
            required_match = sum(
                1 for s in required_skills
                if any(s in cs or cs in s for cs in candidate_skills)
            ) / len(required_skills)
        else:
            required_match = 1.0

        if preferred_skills:
            preferred_match = sum(
                1 for s in preferred_skills
                if any(s in cs or cs in s for cs in candidate_skills)
            ) / len(preferred_skills)
        else:
            preferred_match = 0.5

        skills_score = (required_match * 0.75 + preferred_match * 0.25) * 100

        # Experience match (35%)
        exp_required = jd_raw.get("experience_min", 0) or 0
        exp_candidate = parsed_profile.get("exp_years", 0) or 0
        if exp_required == 0:
            exp_score = 100
        elif exp_candidate >= exp_required:
            exp_score = min(100, 80 + (exp_candidate - exp_required) * 4)
        else:
            exp_score = max(0, (exp_candidate / exp_required) * 70)

        # Qualification match (25%) — simple heuristic
        education = (parsed_profile.get("education") or "").lower()
        if any(kw in education for kw in ["phd", "doctorate"]):
            qual_score = 100
        elif any(kw in education for kw in ["master", "m.tech", "mba", "m.sc"]):
            qual_score = 90
        elif any(kw in education for kw in ["bachelor", "b.tech", "b.e", "b.sc", "b.com"]):
            qual_score = 75
        elif any(kw in education for kw in ["diploma", "associate"]):
            qual_score = 50
        else:
            qual_score = 40

        # Weighted total
        fit_score = round(
            skills_score * 0.40 + exp_score * 0.35 + qual_score * 0.25, 2
        )

        return {
            "fit_score": fit_score,
            "score_breakdown": {
                "skills_match": round(skills_score, 2),
                "exp_match": round(exp_score, 2),
                "qual_match": round(qual_score, 2),
            },
            "score_explanation": (
                f"Skills: {round(skills_score)}% | "
                f"Experience: {round(exp_score)}% | "
                f"Qualifications: {round(qual_score)}%"
            ),
        }
