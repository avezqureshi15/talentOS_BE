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
<div style="font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; color: #1f2937; line-height: 1.55;">
  <p>Hi {candidate_name},</p>
  <p>
    Your AI interview for the <strong>{role_title}</strong> role is ready.
    Use the button below to start whenever you are prepared — you can take it
    at your own convenience within the interview window.
  </p>
  <p style="margin: 24px 0;">
    <a href="{interview_url}"
       style="background: #4f46e5; color: #ffffff; padding: 12px 20px;
              text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block;">
      Start AI Interview
    </a>
  </p>
  <p>Or copy this link into your browser:<br/>
    <a href="{interview_url}">{interview_url}</a>
  </p>
  <ul>
    <li>Use a laptop/desktop with a stable internet connection.</li>
    <li>Allow microphone access when prompted.</li>
    <li>Find a quiet space; the interview typically takes 20-30 minutes.</li>
  </ul>
  <p>If you have any trouble, reply to this email.</p>
  <p>Best,<br/>The Hiring Team</p>
</div>
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
