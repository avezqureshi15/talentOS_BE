from app.core.config import settings

_SUBJECT = "Submit your interview feedback"
_REMINDER_SUBJECT = "Reminder: Submit your interview feedback"
_PREHEADER = "Open the form to share your review for the candidate"
_CTA_TEXT = "Submit Review"
_FOOTER_NOTE = "TalentOS"

_BODY_INTRO = (
    "Please submit your feedback for the candidate you recently interviewed. "
    "Use the button below to open the review form."
)
_BODY_REMINDER_INTRO = (
    "This is a reminder to submit your feedback for the candidate you recently interviewed. "
    "Use the button below to open the review form."
)
_EXPIRY_NOTE = f"This link expires in {settings.FORM_EXPIRY_HOURS} hours."

_PARA_STYLE = "font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);margin:0 0 16px;"


def _para(text: str) -> str:
    return f'<p style="{_PARA_STYLE}">{text}</p>'


def render_review_form_email(
    *,
    recipient_name: str,
    candidate_name: str,
    form_url: str,
    round_name: str | None = None,
    scheduled_at_label: str | None = None,
    is_reminder: bool = False,
) -> tuple[str, str, str]:
    subject = _REMINDER_SUBJECT if is_reminder else _SUBJECT
    intro = _BODY_REMINDER_INTRO if is_reminder else _BODY_INTRO

    body_html = _para(intro)
    body_html += f'<p style="{_PARA_STYLE}"><strong>Candidate:</strong> {candidate_name}</p>'
    if round_name:
        body_html += f'<p style="{_PARA_STYLE}"><strong>Round:</strong> {round_name}</p>'
    if scheduled_at_label:
        body_html += f'<p style="{_PARA_STYLE}"><strong>Interview time:</strong> {scheduled_at_label}</p>'
    body_html += _para(_EXPIRY_NOTE)

    prefix = "This is a reminder. " if is_reminder else ""
    details = f"\nRound: {round_name}" if round_name else ""
    if scheduled_at_label:
        details += f"\nInterview time: {scheduled_at_label}"
    plain = (
        f"Hi {recipient_name},\n\n"
        f"{prefix}Please submit your feedback for {candidate_name}.{details}\n\n"
        f"{form_url}\n\n"
        f"{_EXPIRY_NOTE}\n\n"
        "Regards,\nTalentOS"
    )

    return subject, plain, body_html
