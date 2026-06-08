"""
JD generation service.
Uses Claude Sonnet to generate a full job description
from structured hiring request fields.
"""
import anthropic
from app.core.config import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


class JDService:
    @staticmethod
    async def generate(
        stream: str,
        band: str,
        designation: str,
        experience_min: int,
        skills_required: list,
        urgency: str,
        employment_type: str,
        role_expectations: str = "",
    ) -> str:
        skills_text = ", ".join(
            [
                f"{s['skill']} ({'required' if s.get('priority') == 'required' else 'preferred'})"
                for s in skills_required
            ]
        )

        prompt = f"""You are an expert HR professional at Webknot Technologies.
Generate a complete, professional job description for the following role.

Role Details:
- Stream: {stream}
- Band: {band}
- Designation: {designation}
- Employment Type: {employment_type}
- Minimum Experience: {experience_min} years
- Skills: {skills_text}
- Urgency: {urgency}
{f'- Role Expectations: {role_expectations}' if role_expectations else ''}

Write a complete JD including:
1. About the Role (2-3 sentences)
2. Key Responsibilities (6-8 bullet points)
3. Required Skills (from the skills list)
4. Preferred Skills
5. What We Offer (keep it brief, 3-4 points)

Keep it professional, specific, and appealing to strong candidates.
Do not include salary information.
"""

        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        return message.content[0].text
