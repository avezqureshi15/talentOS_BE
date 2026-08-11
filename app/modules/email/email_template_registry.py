"""Registry of every application email template.

This is the single source of truth that the Email Manager lists. Each template
stores an editable ``subject_template`` and a content-only ``body_html_template``
(the message body). The branded dark shell (header, button, footer) is applied
at render time by ``build_email_html``, so users only ever edit the message text.

Placeholders use ``{{key}}`` delimiters (NOT Python ``str.format`` braces) so
they can never collide with CSS braces inside the HTML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

PLACEHOLDER_OPEN = "{{"
PLACEHOLDER_CLOSE = "}}"


def tokenize(key: str) -> str:
    return f"{PLACEHOLDER_OPEN}{key}{PLACEHOLDER_CLOSE}"


def format_template(text: str, context: dict[str, str]) -> str:
    """Replace ``{{key}}`` tokens with values. Unknown tokens are left as-is."""
    for key, value in context.items():
        text = text.replace(tokenize(key), str(value))
    return text


RenderFn = Callable[[dict[str, str]], tuple[str, str, str]]

_DEFAULT_FOOTER = "TalentOS - AI-powered recruitment intelligence."


@dataclass(frozen=True)
class TemplateSpec:
    key: str
    name: str
    description: str
    is_editable: bool
    placeholders: tuple[str, ...]
    sample_context: dict[str, str]
    default_render: RenderFn
    preheader: str
    cta_text: str
    cta_url_placeholder: str | None
    recipient_placeholder: str | None
    footer_note: str = _DEFAULT_FOOTER
    default_version: int = 1
    _defaults: tuple[str, str] | None = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_defaults", None)

    def _get_defaults(self) -> tuple[str, str]:
        if self._defaults is None:
            tokens = {k: tokenize(k) for k in self.placeholders}
            subject, _plain, html = self.default_render({**self.sample_context, **tokens})
            object.__setattr__(self, "_defaults", (subject, html))
        return self._defaults

    @property
    def default_subject(self) -> str:
        return self._get_defaults()[0]

    @property
    def default_html(self) -> str:
        return self._get_defaults()[1]


def build_email_html(spec: TemplateSpec, context: dict[str, str], subject: str, content: str) -> str:
    """Wrap content-only message HTML in the branded TalentOS email shell."""
    from app.common.services.email_templates import render_talentos_email

    recipient = context.get(spec.recipient_placeholder) if spec.recipient_placeholder else None
    if not recipient:
        recipient = context.get("recipient_name") or "there"
    cta_url = context.get(spec.cta_url_placeholder) if spec.cta_url_placeholder else None
    return render_talentos_email(
        subject=subject,
        preheader=spec.preheader,
        recipient_name=recipient,
        body_html=content,
        cta_url=cta_url,
        cta_text=spec.cta_text,
        footer_note=spec.footer_note,
    )


# Default renderers (thin closures over the existing code functions).
# All return content-only HTML; the shell is applied by ``build_email_html``.


def _make_slot_form_renderer(is_reminder: bool) -> RenderFn:
    def render(context: dict[str, str]) -> tuple[str, str, str]:
        from app.common.email_templates.slot_form import render_slot_form_email

        return render_slot_form_email(
            recipient_name=context.get("recipient_name", "there"),
            requester_name=context.get("requester_name"),
            form_url=context.get("form_url", "https://app.talentos.ai"),
            is_reminder=is_reminder,
        )

    return render


def _make_review_form_renderer(is_reminder: bool) -> RenderFn:
    def render(context: dict[str, str]) -> tuple[str, str, str]:
        from app.common.email_templates.review_form import render_review_form_email

        return render_review_form_email(
            recipient_name=context.get("recipient_name", "there"),
            candidate_name=context.get("candidate_name", "the candidate"),
            round_name=context.get("round_name", "the interview"),
            scheduled_at_label=context.get("scheduled_at_label", "the scheduled time"),
            form_url=context.get("form_url", "https://app.talentos.ai"),
            is_reminder=is_reminder,
        )

    return render


def _render_interview_invite(context: dict[str, str]) -> tuple[str, str, str]:
    from app.modules.hiring_requests.ai_interview_mail_templates import render_interview_invite_email

    return render_interview_invite_email(
        candidate_name=context.get("candidate_name", "there"),
        role_title=context.get("role_title", "the role"),
        interview_url=context.get("interview_url", "https://app.talentos.ai/interview"),
    )


def _render_interview_slot(context: dict[str, str]) -> tuple[str, str, str]:
    from app.modules.hiring_requests.ai_interview_mail_templates import render_interview_slot_email

    return render_interview_slot_email(
        candidate_name=context.get("candidate_name", "there"),
        role_title=context.get("role_title", "the role"),
        interview_url=context.get("interview_url", "https://app.talentos.ai/interview"),
        scheduled_at_label=context.get(
            "scheduled_at_label", "Monday, 21 July 2026 at 4:00 PM IST"
        ),
    )


def _render_invite(context: dict[str, str]) -> tuple[str, str, str]:
    subject = f"You're invited to join {context.get('organization_name', 'TalentOS')}"
    body = f"""Hello {context.get('recipient_email', 'there')},

{context.get('inviter_name', 'A team member')} has invited you to join
{context.get('organization_name', 'TalentOS')} on TalentOS.

Click the link below to set up your account:

{context.get('link', 'https://app.talentos.ai')}

This invite expires in 7 days.

If you did not expect this invitation, you can ignore this email.

Best,
The TalentOS Team"""
    html = (
        '<p style="font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);margin:0 0 16px;">'
        f"{context.get('inviter_name', 'A team member')} has invited you to join "
        f"<strong>{context.get('organization_name', 'TalentOS')}</strong> on TalentOS. "
        "Click the button below to set up your account:</p>"
    )
    return subject, body, html


# The full catalogue


EMAIL_TEMPLATES: tuple[TemplateSpec, ...] = (
    TemplateSpec(
        key="slot_form",
        name="Submit Your Availability",
        description="Sent to an employee so they can share their available slots.",
        is_editable=True,
        placeholders=("recipient_name", "requester_name", "form_url"),
        sample_context={
            "recipient_name": "Alex Carter",
            "requester_name": "Sam Rivera",
            "form_url": "https://app.talentos.ai/book-slot/abc123",
        },
        default_render=_make_slot_form_renderer(is_reminder=False),
        preheader="Open the form to share your available slots",
        cta_text="Submit Availability",
        cta_url_placeholder="form_url",
        recipient_placeholder="recipient_name",
        footer_note="TalentOS",
        default_version=4,
    ),
    TemplateSpec(
        key="slot_form_reminder",
        name="Reminder: Submit Your Availability",
        description="Reminder sent to an employee who has not shared their slots yet.",
        is_editable=True,
        placeholders=("recipient_name", "requester_name", "form_url"),
        sample_context={
            "recipient_name": "Alex Carter",
            "requester_name": "Sam Rivera",
            "form_url": "https://app.talentos.ai/book-slot/abc123",
        },
        default_render=_make_slot_form_renderer(is_reminder=True),
        preheader="Open the form to share your available slots",
        cta_text="Submit Availability",
        cta_url_placeholder="form_url",
        recipient_placeholder="recipient_name",
        footer_note="TalentOS",
        default_version=4,
    ),
    TemplateSpec(
        key="review_form",
        name="Submit Your Interview Feedback",
        description="Sent to an interviewer asking them to submit feedback for a candidate.",
        is_editable=True,
        placeholders=("recipient_name", "candidate_name", "round_name", "scheduled_at_label", "form_url"),
        sample_context={
            "recipient_name": "Sam Rivera",
            "candidate_name": "Priya Sharma",
            "round_name": "Technical Interview",
            "scheduled_at_label": "Tuesday, 28 July 2026 at 3:00 PM IST",
            "form_url": "https://app.talentos.ai/rate-candidate/xyz789",
        },
        default_render=_make_review_form_renderer(is_reminder=False),
        preheader="Open the form to share your review for the candidate",
        cta_text="Submit Review",
        cta_url_placeholder="form_url",
        recipient_placeholder="recipient_name",
        footer_note="TalentOS",
        default_version=4,
    ),
    TemplateSpec(
        key="review_form_reminder",
        name="Reminder: Submit Your Interview Feedback",
        description="Reminder sent to an interviewer who has not submitted feedback yet.",
        is_editable=True,
        placeholders=("recipient_name", "candidate_name", "round_name", "scheduled_at_label", "form_url"),
        sample_context={
            "recipient_name": "Sam Rivera",
            "candidate_name": "Priya Sharma",
            "round_name": "Technical Interview",
            "scheduled_at_label": "Tuesday, 28 July 2026 at 3:00 PM IST",
            "form_url": "https://app.talentos.ai/rate-candidate/xyz789",
        },
        default_render=_make_review_form_renderer(is_reminder=True),
        preheader="Open the form to share your review for the candidate",
        cta_text="Submit Review",
        cta_url_placeholder="form_url",
        recipient_placeholder="recipient_name",
        footer_note="TalentOS",
        default_version=4,
    ),
    TemplateSpec(
        key="interview_invite",
        name="AI Interview Invitation",
        description="Sent to a candidate inviting them to take an AI interview.",
        is_editable=True,
        placeholders=("candidate_name", "role_title", "interview_url"),
        sample_context={
            "candidate_name": "Jordan Lee",
            "role_title": "Frontend Engineer",
            "interview_url": "https://app.talentos.ai/ai-interview/room123",
        },
        default_render=_render_interview_invite,
        preheader="Your AI interview is ready to start.",
        cta_text="Start AI Interview",
        cta_url_placeholder="interview_url",
        recipient_placeholder="candidate_name",
        default_version=4,
    ),
    TemplateSpec(
        key="interview_slot",
        name="AI Interview Scheduled",
        description="Sent to a candidate confirming the scheduled time for their AI interview.",
        is_editable=True,
        placeholders=("candidate_name", "role_title", "interview_url", "scheduled_at_label"),
        sample_context={
            "candidate_name": "Jordan Lee",
            "role_title": "Frontend Engineer",
            "interview_url": "https://app.talentos.ai/ai-interview/room123",
            "scheduled_at_label": "Monday, 21 July 2026 at 4:00 PM IST",
        },
        default_render=_render_interview_slot,
        preheader="Your AI interview has been scheduled.",
        cta_text="Start AI Interview",
        cta_url_placeholder="interview_url",
        recipient_placeholder="candidate_name",
        default_version=4,
    ),
    TemplateSpec(
        key="invite",
        name="Invitation to Join TalentOS",
        description="Sent to a new user inviting them to join the TalentOS workspace.",
        is_editable=True,
        placeholders=("recipient_email", "organization_name", "inviter_name", "link"),
        sample_context={
            "recipient_email": "dana@example.com",
            "organization_name": "Acme Corp",
            "inviter_name": "Sam Rivera",
            "link": "https://app.talentos.ai/auth/invite/abcd1234",
        },
        default_render=_render_invite,
        preheader="You've been invited to join the TalentOS workspace.",
        cta_text="Accept Invite",
        cta_url_placeholder="link",
        recipient_placeholder="recipient_email",
        default_version=4,
    ),
)


EMAIL_TEMPLATE_MAP: dict[str, TemplateSpec] = {t.key: t for t in EMAIL_TEMPLATES}


def get_template_spec(key: str) -> TemplateSpec | None:
    return EMAIL_TEMPLATE_MAP.get(key)


def all_template_specs() -> list[TemplateSpec]:
    return list(EMAIL_TEMPLATES)
