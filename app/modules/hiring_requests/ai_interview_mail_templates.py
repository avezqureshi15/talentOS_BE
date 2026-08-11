"""Static email content for AI-interview invitations. No hardcoded copy in the helper."""

from __future__ import annotations

SUBJECT_TEMPLATE = "Your AI interview for {role_title}"

BODY_TEXT_TEMPLATE = (
    "Hi {candidate_name},\n\n"
    "Your AI interview for the {role_title} role is ready. "
    "Use the link below to start whenever you are prepared — "
    "you can take it at your own convenience within the interview window.\n\n"
    "Join link: {interview_url}\n\n"
    "A few things to know:\n"
    "  - Please use a laptop/desktop with a stable internet connection.\n"
    "  - Allow microphone access when prompted.\n"
    "  - Find a quiet space; the interview typically takes 20-30 minutes.\n\n"
    "If you have any trouble, reply to this email.\n\n"
    "Best,\n"
    "The Hiring Team"
)

BODY_HTML_TEMPLATE = """
  <p style="font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);margin:0;">
    Your AI interview for the <strong>{role_title}</strong> role is ready.
    Use the button below to start whenever you are prepared — you can take it
    at your own convenience within the interview window.
  </p>
  <p style="font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);margin:20px 0 0;">
    Or copy this link into your browser:<br/>
    <a href="{interview_url}" style="color:#818CF8;word-break:break-all;">{interview_url}</a>
  </p>
  <ul style="margin:16px 0 0;padding-left:20px;font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);">
    <li>Use a laptop/desktop with a stable internet connection.</li>
    <li>Allow microphone access when prompted.</li>
    <li>Find a quiet space; the interview typically takes 20-30 minutes.</li>
  </ul>
  <p style="font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);margin:20px 0 0;">If you have any trouble, reply to this email.</p>
  <p style="font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);margin:16px 0 0;">Best,<br/>The Hiring Team</p>
"""


def render_interview_invite_email(
    candidate_name: str,
    role_title: str,
    interview_url: str,
) -> tuple[str, str, str]:
    fmt = {
        "candidate_name": candidate_name,
        "role_title": role_title,
        "interview_url": interview_url,
    }
    subject = SUBJECT_TEMPLATE.format(**fmt)
    body = BODY_TEXT_TEMPLATE.format(**fmt)
    html = BODY_HTML_TEMPLATE.format(**fmt)
    return subject, body, html


SUBJECT_SLOT_TEMPLATE = "Your AI interview for {role_title} is scheduled"

BODY_SLOT_TEXT_TEMPLATE = (
    "Hi {candidate_name},\n\n"
    "Your AI interview for the {role_title} role is scheduled for {scheduled_at_label}.\n\n"
    "The interview link opens at the scheduled time — please join a few minutes early "
    "to check your microphone and camera.\n\n"
    "Join link: {interview_url}\n\n"
    "A few things to know:\n"
    "  - Please use a laptop/desktop with a stable internet connection.\n"
    "  - Allow microphone access when prompted.\n"
    "  - Find a quiet space; the interview typically takes 20-30 minutes.\n\n"
    "If you have any trouble, reply to this email.\n\n"
    "Best,\n"
    "The Hiring Team"
)

BODY_SLOT_HTML_TEMPLATE = """
  <p style="font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);margin:0;">
    Your AI interview for the <strong>{role_title}</strong> role is scheduled for
    <strong>{scheduled_at_label}</strong>.
  </p>
  <p style="font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);margin:16px 0 0;">
    The interview link opens at the scheduled time — please join a few minutes early
    to check your microphone and camera.
  </p>
  <p style="font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);margin:20px 0 0;">
    Or copy this link into your browser:<br/>
    <a href="{interview_url}" style="color:#818CF8;word-break:break-all;">{interview_url}</a>
  </p>
  <ul style="margin:16px 0 0;padding-left:20px;font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);">
    <li>Use a laptop/desktop with a stable internet connection.</li>
    <li>Allow microphone access when prompted.</li>
    <li>Find a quiet space; the interview typically takes 20-30 minutes.</li>
  </ul>
  <p style="font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);margin:20px 0 0;">If you have any trouble, reply to this email.</p>
  <p style="font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);margin:16px 0 0;">Best,<br/>The Hiring Team</p>
"""


def render_interview_slot_email(
    candidate_name: str,
    role_title: str,
    interview_url: str,
    scheduled_at_label: str,
) -> tuple[str, str, str]:
    fmt = {
        "candidate_name": candidate_name,
        "role_title": role_title,
        "interview_url": interview_url,
        "scheduled_at_label": scheduled_at_label,
    }
    subject = SUBJECT_SLOT_TEMPLATE.format(**fmt)
    body = BODY_SLOT_TEXT_TEMPLATE.format(**fmt)
    html = BODY_SLOT_HTML_TEMPLATE.format(**fmt)
    return subject, body, html
