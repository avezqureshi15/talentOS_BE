from app.core.config import settings
from app.common.services.email_templates import block_text, render_talentos_email

_SUBJECT = "Submit Your Availability"
_REMINDER_SUBJECT = "Reminder: Submit Your Availability"
_PREHEADER = "Open the form to share your available slots"
_CTA_TEXT = "Submit Availability"
_FOOTER_NOTE = "webHyre.ai"

_BODY_INTRO = (
    "Please share your availability using the button below to open the slot submission form."
)
_BODY_REMINDER_INTRO = (
    "This is a reminder to share your availability. "
    "Use the button below to open the slot submission form."
)
_EXPIRY_NOTE = f"This link expires in {settings.FORM_EXPIRY_HOURS} hours."


def render_slot_form_email(*, recipient_name: str, form_url: str, is_reminder: bool = False) -> tuple[str, str, str]:
    subject = _REMINDER_SUBJECT if is_reminder else _SUBJECT
    intro = _BODY_REMINDER_INTRO if is_reminder else _BODY_INTRO

    body_html = block_text(intro) + block_text(_EXPIRY_NOTE)

    html = render_talentos_email(
        subject=subject,
        preheader=_PREHEADER,
        recipient_name=recipient_name,
        body_html=body_html,
        cta_url=form_url,
        cta_text=_CTA_TEXT,
        footer_note=_FOOTER_NOTE,
    )

    prefix = "This is a reminder. " if is_reminder else ""
    plain = (
        f"Hi {recipient_name},\n\n"
        f"{prefix}{_BODY_INTRO}\n\n"
        f"{form_url}\n\n"
        f"{_EXPIRY_NOTE}\n\n"
        "Regards,\nwebHyre.ai"
    )

    return subject, plain, html
