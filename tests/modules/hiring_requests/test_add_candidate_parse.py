from types import SimpleNamespace
from unittest.mock import patch

from app.common.clients import AIClientError
from app.modules.hiring_requests.add_candidate_service import (
    MAX_RESUME_PARSE_CHARS,
    MAX_RESUME_PARSE_PAGES,
    _cap_resume_text,
    _extract_text,
    _parse_resume_fields,
)


def test_cap_resume_text_slices_to_limit():
    raw = "a" * (MAX_RESUME_PARSE_CHARS + 50)
    capped = _cap_resume_text(raw)
    assert len(capped) == MAX_RESUME_PARSE_CHARS
    assert capped == raw[:MAX_RESUME_PARSE_CHARS]


def test_cap_resume_text_leaves_short_text_alone():
    raw = "Ada Lovelace\nada@example.com"
    assert _cap_resume_text(raw) == raw


@patch("app.modules.hiring_requests.add_candidate_service.PdfReader")
def test_extract_text_reads_only_first_pages(mock_reader):
    pages = [SimpleNamespace(extract_text=lambda i=i: f"PAGE{i}\n") for i in range(7)]
    mock_reader.return_value = SimpleNamespace(pages=pages)

    text = _extract_text(b"%PDF-fake")
    assert "PAGE0" in text
    assert "PAGE4" in text
    assert "PAGE5" not in text
    assert "PAGE6" not in text
    assert MAX_RESUME_PARSE_PAGES == 5


@patch("app.modules.hiring_requests.add_candidate_service.PdfReader")
def test_extract_text_caps_characters(mock_reader):
    huge = "x" * (MAX_RESUME_PARSE_CHARS + 100)
    mock_reader.return_value = SimpleNamespace(
        pages=[SimpleNamespace(extract_text=lambda: huge)]
    )
    text = _extract_text(b"%PDF-fake")
    assert len(text) == MAX_RESUME_PARSE_CHARS


@patch("app.modules.hiring_requests.add_candidate_service.AIClient")
@patch("app.modules.hiring_requests.add_candidate_service._extract_text")
def test_ai_fields_fill_missing_values(mock_extract, mock_ai):
    mock_extract.return_value = "some resume body"
    mock_ai.return_value.generate.return_value = SimpleNamespace(
        result={
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "+1 (202) 555-0147",
            "linkedin_url": "linkedin.com/in/adalovelace",
        }
    )

    name, email, phone, linkedin = _parse_resume_fields(b"pdf", "", "", "")
    assert name == "Ada Lovelace"
    assert email == "ada@example.com"
    assert phone == "2025550147"
    assert linkedin == "https://linkedin.com/in/adalovelace"
    mock_ai.return_value.generate.assert_called_once()
    sent = mock_ai.return_value.generate.call_args.kwargs["input_data"]["resume_text"]
    assert sent == "some resume body"


@patch("app.modules.hiring_requests.add_candidate_service.AIClient")
@patch("app.modules.hiring_requests.add_candidate_service._extract_text")
def test_form_values_win_over_ai(mock_extract, mock_ai):
    mock_extract.return_value = "Jane Doe\njane@example.com"
    mock_ai.return_value.generate.return_value = SimpleNamespace(
        result={
            "name": "AI Name",
            "email": "ai@example.com",
            "phone": "1111111111",
            "linkedin_url": "https://linkedin.com/in/ai",
        }
    )

    name, email, phone, linkedin = _parse_resume_fields(
        b"pdf",
        "Form Name",
        "form@example.com",
        "8888888888",
        "https://linkedin.com/in/form",
    )
    mock_extract.assert_not_called()
    mock_ai.assert_not_called()
    assert name == "Form Name"
    assert email == "form@example.com"
    assert phone == "8888888888"
    assert linkedin == "https://linkedin.com/in/form"


@patch("app.modules.hiring_requests.add_candidate_service.AIClient")
@patch("app.modules.hiring_requests.add_candidate_service._extract_text")
def test_partial_form_fields_still_call_ai(mock_extract, mock_ai):
    mock_extract.return_value = "body"
    mock_ai.return_value.generate.return_value = SimpleNamespace(
        result={
            "name": "AI Name",
            "email": "ai@example.com",
            "phone": "1111111111",
            "linkedin_url": "https://linkedin.com/in/ai",
        }
    )

    name, email, phone, linkedin = _parse_resume_fields(
        b"pdf",
        "Form Name",
        "",
        "",
    )
    assert name == "Form Name"
    assert email == "ai@example.com"
    assert phone == "1111111111"
    assert linkedin == "https://linkedin.com/in/ai"


@patch("app.modules.hiring_requests.add_candidate_service.AIClient")
@patch("app.modules.hiring_requests.add_candidate_service._extract_text")
def test_regex_fallback_when_ai_fails(mock_extract, mock_ai):
    mock_extract.return_value = (
        "Grace Hopper\ngrace@navy.mil\n+1 202-555-0100\nhttps://www.linkedin.com/in/gracehopper"
    )
    mock_ai.return_value.generate.side_effect = AIClientError(
        message="AI service unreachable",
        status_code=502,
    )

    name, email, phone, linkedin = _parse_resume_fields(b"pdf", "", "", "")
    assert name == "Grace Hopper"
    assert email == "grace@navy.mil"
    assert phone == "2025550100"
    assert "linkedin.com/in/gracehopper" in linkedin
