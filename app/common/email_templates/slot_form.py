from app.core.config import settings

_SUBJECT = "Submit Your Availability"
_REMINDER_SUBJECT = "Reminder: Submit Your Availability"
_PREHEADER = "Open the form to share your available slots"
_CTA_TEXT = "Submit Availability"
_FOOTER_NOTE = "TalentOS"

_BODY_INTRO = (
    "Please share your availability using the button below to open the slot submission form."
)
_BODY_REMINDER_INTRO = (
    "This is a reminder to share your availability. "
    "Use the button below to open the slot submission form."
)
_EXPIRY_NOTE = f"This link expires in {settings.FORM_EXPIRY_HOURS} hours."

_PARA_STYLE = "font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);margin:0 0 16px;"


def _para(text: str) -> str:
    return f'<p style="{_PARA_STYLE}">{text}</p>'


def render_slot_form_email(
    *, recipient_name: str, form_url: str, requester_name: str | None = None, is_reminder: bool = False
) -> tuple[str, str, str]:
    subject = _REMINDER_SUBJECT if is_reminder else _SUBJECT
    intro = _BODY_REMINDER_INTRO if is_reminder else _BODY_INTRO

    body_html = _para(intro)
    if requester_name:
        body_html += f'<p style="{_PARA_STYLE}"><strong>Requested by:</strong> {requester_name}</p>'
    body_html += _para(_EXPIRY_NOTE)

    prefix = "This is a reminder. " if is_reminder else ""
    requester_line = f"\n\nRequested by: {requester_name}" if requester_name else ""
    plain = (
        f"Hi {recipient_name},\n\n"
        f"{prefix}{_BODY_INTRO}\n\n"
        f"{form_url}\n\n"
        f"{_EXPIRY_NOTE}{requester_line}\n\n"
        "Regards,\nTalentOS"
    )

    return subject, plain, body_html
