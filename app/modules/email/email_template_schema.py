from datetime import datetime

from pydantic import BaseModel


class EmailTemplateSummary(BaseModel):
    key: str
    name: str
    description: str | None = None
    is_editable: bool
    updated_at: datetime
    updated_by: str | None = None


class EmailTemplateDetail(EmailTemplateSummary):
    subject_template: str
    body_html_template: str
    placeholders: list[str] = []
    sample_context: dict[str, str] = {}


class EmailTemplateListResponse(BaseModel):
    templates: list[EmailTemplateSummary]


class UpdateEmailTemplateRequest(BaseModel):
    subject_template: str
    body_html_template: str


class PreviewEmailTemplateRequest(BaseModel):
    key: str | None = None
    subject_template: str | None = None
    body_html_template: str | None = None


class PreviewEmailTemplateResponse(BaseModel):
    key: str
    subject: str
    html: str


class TestEmailTemplateRequest(BaseModel):
    to_email: str | None = None


class TestEmailTemplateResponse(BaseModel):
    success: bool
    message: str
    to_email: str
