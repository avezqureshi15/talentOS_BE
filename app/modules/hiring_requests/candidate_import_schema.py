from pydantic import BaseModel


class ImportRow(BaseModel):
    name: str
    email: str
    phone: str | None = None
    resume_url: str


class ImportCandidatesResponse(BaseModel):
    created: int = 0
    skipped: int = 0
    errors: list[dict] = []
    total: int = 0
