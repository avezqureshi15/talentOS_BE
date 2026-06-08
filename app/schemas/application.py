from pydantic import BaseModel, EmailStr
from uuid import UUID


class ApplicationSubmitIn(BaseModel):
    job_posting_id: UUID
    name: str
    phone: str
    email: EmailStr
    resume_url: str   # URL from careers page Supabase Storage


class ApplicationSubmitOut(BaseModel):
    message: str = "Application received! We'll be in touch."
    candidate_id: UUID
