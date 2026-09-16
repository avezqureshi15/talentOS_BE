from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.common.clients import AIClientError
from app.modules.hiring_requests.jd_parse_service import (
    MAX_JD_PARSE_CHARS,
    MAX_JD_PARSE_PAGES,
    _cap_jd_text,
    _extract_text,
    _normalize_type,
    _to_parsed,
    parse_jd_file,
)


def test_cap_jd_text_slices_to_limit():
    raw = "a" * (MAX_JD_PARSE_CHARS + 10)
    assert len(_cap_jd_text(raw)) == MAX_JD_PARSE_CHARS


def test_normalize_type_maps_aliases():
    assert _normalize_type("full time") == "Full-time"
    assert _normalize_type("FULL-TIME") == "Full-time"
    assert _normalize_type("Internship") == "Internship"
    assert _normalize_type("contractor") == ""
    assert _normalize_type("") == ""


def test_to_parsed_coerces_lists_and_truncates():
    parsed = _to_parsed(
        {
            "title": "  Backend Engineer  ",
            "department": "Engineering",
            "type": "full-time",
            "location": ["Bangalore", " ", "Remote"],
            "description": "Build APIs",
            "requirements": ["Python", ""],
            "benefits": "Health\nPF",
            "custom_evaluation_criteria": "Must know FastAPI",
        }
    )
    assert parsed.title == "Backend Engineer"
    assert parsed.type == "Full-time"
    assert parsed.location == ["Bangalore", "Remote"]
    assert parsed.requirements == ["Python"]
    assert parsed.benefits == ["Health", "PF"]


@patch("app.modules.hiring_requests.jd_parse_service.PdfReader")
def test_extract_text_reads_only_first_pages(mock_reader):
    pages = [SimpleNamespace(extract_text=lambda i=i: f"PAGE{i}\n") for i in range(7)]
    mock_reader.return_value = SimpleNamespace(pages=pages)
    text = _extract_text(b"%PDF-fake")
    assert "PAGE0" in text
    assert "PAGE4" in text
    assert "PAGE5" not in text
    assert MAX_JD_PARSE_PAGES == 5


def test_parse_jd_rejects_non_pdf():
    upload = SimpleNamespace(filename="jd.docx", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", file=MagicMock())
    upload.file.read.return_value = b"not-a-pdf"
    with pytest.raises(HTTPException) as exc:
        parse_jd_file(upload)
    assert exc.value.status_code == 400
    assert "PDF" in exc.value.detail


@patch("app.modules.hiring_requests.jd_parse_service._extract_text", return_value="Senior Backend Engineer\nBangalore\n")
@patch("app.modules.hiring_requests.jd_parse_service.AIClient")
def test_parse_jd_uses_ai_result(mock_ai, _extract):
    mock_ai.return_value.generate.return_value = SimpleNamespace(
        result={
            "title": "Senior Backend Engineer",
            "department": "Engineering",
            "type": "Full-time",
            "location": ["Bangalore"],
            "description": "Own the API layer",
            "requirements": ["Python"],
            "benefits": ["Health"],
            "custom_evaluation_criteria": "5+ years Python",
        }
    )
    upload = SimpleNamespace(filename="jd.pdf", content_type="application/pdf", file=MagicMock())
    upload.file.read.return_value = b"%PDF"
    parsed = parse_jd_file(upload)
    assert parsed.title == "Senior Backend Engineer"
    assert parsed.location == ["Bangalore"]
    mock_ai.return_value.generate.assert_called_once()


@patch("app.modules.hiring_requests.jd_parse_service._extract_text", return_value="some jd")
@patch("app.modules.hiring_requests.jd_parse_service.AIClient")
def test_parse_jd_surfaces_ai_failure(mock_ai, _extract):
    mock_ai.return_value.generate.side_effect = AIClientError(
        message="AI service returned 500: An unexpected error occurred.",
        status_code=500,
    )
    upload = SimpleNamespace(filename="jd.pdf", content_type="application/pdf", file=MagicMock())
    upload.file.read.return_value = b"%PDF"
    with pytest.raises(HTTPException) as exc:
        parse_jd_file(upload)
    assert exc.value.status_code == 500
