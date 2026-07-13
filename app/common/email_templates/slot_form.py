from app.core.config import settings
from app.common.services.email_templates import block_text, render_talentos_email

_SUBJECT = "Submit Your Availability"
_PREHEADER = "Open the form to share your available slots"
_CTA_TEXT = "Submit Availability"
_FOOTER_NOTE = "webHyre.ai"

_BODY_INTRO = (
    "Please share your availability using the button below to open the slot submission form."
)
_EXPIRY_NOTE = f"This link expires in {settings.FORM_EXPIRY_HOURS} hours."


def render_slot_form_email(*, recipient_name: str, form_url: str) -> tuple[str, str, str]:
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
        f"{_BODY_INTRO}\n\n"
        f"{form_url}\n\n"
        f"{_EXPIRY_NOTE}\n\n"
        "Regards,\nwebHyre.ai"
    )

    return _SUBJECT, plain, html
