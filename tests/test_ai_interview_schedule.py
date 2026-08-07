import pytest
from unittest.mock import AsyncMock, patch

from app.core.ai_recruitment_client import AiRecruitmentClient
from app.modules.hiring_requests.ai_interview_mail import (
    format_scheduled_slot_label,
    send_interview_slot_email,
    send_interview_invite_email,
)
from app.modules.hiring_requests.ai_interview_mail_templates import (
    render_interview_slot_email,
)


def test_slot_template_renders_label_and_url():
    subject, body, html = render_interview_slot_email(
        candidate_name="Ada",
        role_title="Backend Engineer",
        interview_url="https://poc.example/interview/tok",
        scheduled_at_label="Monday, 21 July 2026 at 4:00 PM IST",
    )
    assert "is scheduled" in subject
    assert "Monday, 21 July 2026 at 4:00 PM IST" in body
    assert "https://poc.example/interview/tok" in html


def test_format_slot_label_kolkata():
    label = format_scheduled_slot_label("2026-07-21", "16:00", "Asia/Kolkata")
    assert label.startswith("Tuesday, 21 July 2026 at 4:00 PM")
    assert "IST" in label


def test_format_slot_label_missing_parts_empty():
    assert format_scheduled_slot_label(None, "16:00", "Asia/Kolkata") == ""
    assert format_scheduled_slot_label("2026-07-21", None, "Asia/Kolkata") == ""


def test_slot_email_skipped_without_url():
    assert send_interview_slot_email("ada@example.com", "Ada", "Role", None, "label") is False


def test_slot_email_skipped_invalid_email():
    assert send_interview_slot_email("not-an-email", "Ada", "Role", "https://x/t", "label") is False


@pytest.mark.parametrize("fn", [send_interview_invite_email, send_interview_slot_email])
def test_emails_skipped_when_smtp_unconfigured(fn):
    with patch("app.modules.hiring_requests.ai_interview_mail.settings.SMTP_USERNAME", ""):
        with patch("app.modules.hiring_requests.ai_interview_mail.settings.SMTP_PASSWORD", ""):
            if fn is send_interview_invite_email:
                assert fn("ada@example.com", "Ada", "Role", "https://x/t") is False
            else:
                assert fn("ada@example.com", "Ada", "Role", "https://x/t", "label") is False


def test_client_schedule_interview_hits_internal_route():
    import asyncio

    client = AiRecruitmentClient()
    with patch.object(client, "_request", new_callable=AsyncMock, return_value={"id": "s1"}) as req:
        result = asyncio.run(
            client.schedule_interview("job1", "cand1", "2026-07-21", "16:00", "Asia/Kolkata")
        )
    assert result == {"id": "s1"}
    assert req.call_args.args[0] == "PUT"
    assert req.call_args.args[1].endswith(
        "/internal/talentos/jobs/job1/candidates/cand1/interview/schedule"
    )
    assert req.call_args.kwargs["json"] == {
        "scheduled_date": "2026-07-21",
        "scheduled_time": "16:00",
        "timezone": "Asia/Kolkata",
    }


def test_client_clear_interview_schedule_uses_same_route():
    import asyncio

    client = AiRecruitmentClient()
    with patch.object(client, "_request", new_callable=AsyncMock, return_value={"id": "s1"}) as req:
        asyncio.run(client.clear_interview_schedule("job1", "cand1"))
    assert req.call_args.args[1].endswith(
        "/internal/talentos/jobs/job1/candidates/cand1/interview/schedule"
    )
    assert req.call_args.kwargs["json"] is None