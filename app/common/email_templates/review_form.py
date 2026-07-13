from app.core.config import settings
from app.common.services.email_templates import block_text, render_talentos_email

_SUBJECT = "Submit your interview feedback"
_PREHEADER = "Open the form to share your review for the candidate"
_CTA_TEXT = "Submit Review"
_FOOTER_NOTE = "webHyre.ai"

_BODY_INTRO = (
    "Please submit your feedback for the candidate you recently interviewed. "
    "Use the button below to open the review form."
)
_EXPIRY_NOTE = f"This link expires in {settings.FORM_EXPIRY_HOURS} hours."


def render_review_form_email(*, recipient_name: str, candidate_name: str, form_url: str) -> tuple[str, str, str]:
    """Returns (subject, plain_text_body, html_body)."""
    body_html = block_text(_BODY_INTRO) + block_text(_EXPIRY_NOTE)

    html = render_talentos_email(
        subject=_SUBJECT,
        preheader=_PREHEADER,
        recipient_name=recipient_name,
        body_html=body_html,
        cta_url=form_url,
        cta_text=_CTA_TEXT,
        footer_note=_FOOTER_NOTE,
    )

    plain = (
        f"Hi {recipient_name},\n\n"
        f"Please submit your feedback for {candidate_name}.\n\n"
        f"{form_url}\n\n"
        f"{_EXPIRY_NOTE}\n\n"
        "Regards,\nwebHyre.ai"
    )

    return _SUBJECT, plain, html
