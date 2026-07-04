from pydantic import BaseModel


class SendEmailRequest(BaseModel):
    to_email: str
    subject: str
    body: str


class SendEmailResponse(BaseModel):
    success: bool
    message: str
