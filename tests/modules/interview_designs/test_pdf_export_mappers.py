from datetime import datetime, timezone
from types import SimpleNamespace

from app.modules.interview_designs.pdf.constants import CHAPTER_INTERVIEW, CHAPTER_SCREENING
from app.modules.interview_designs.pdf.mappers import (
    build_document_spec,
    map_sections_to_chapter,
    safe_filename,
)


def test_map_sections_to_chapter_with_questions():
    sections = [
        {
            "id": "s1",
            "title": "Availability",
            "type": "Q&A",
            "description": "Checks notice.",
            "depth": "Standard",
            "questions": [
                {
                    "id": "q1",
                    "question": "When can you start?",
                    "score": 5,
                    "timeAllocationMinutes": 0.5,
                    "expected_points": ["Clear date"],
                }
            ],
        }
    ]
    chapter = map_sections_to_chapter(CHAPTER_SCREENING, sections)
    assert chapter.title == CHAPTER_SCREENING
    assert "1 sections" in chapter.summary
    assert len(chapter.sections) == 1
    assert chapter.sections[0].eyebrow == "Q&A"
    assert chapter.sections[0].heading.startswith("01.")
    assert len(chapter.sections[0].items) == 1
    assert chapter.sections[0].items[0].bullets == ["Clear date"]


def test_map_empty_sections():
    chapter = map_sections_to_chapter(CHAPTER_INTERVIEW, [])
    assert chapter.sections == []
    assert "0 sections" in chapter.summary


def test_build_document_spec_meta_and_chapters():
    hr = SimpleNamespace(
        title="Senior Golang Developer",
        department="Engineering",
        location="Bangalore",
        type="Full-time",
    )
    generated = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    spec = build_document_spec(hr, [], [{"id": "s", "title": "Tech", "type": "Q&A", "questions": []}], generated_at=generated)
    assert spec.title == "Senior Golang Developer"
    assert spec.subtitle == "Interview Design"
    assert ("Department", "Engineering") in spec.meta
    assert ("Generated", "2026-08-07 12:00 UTC") in spec.meta
    assert len(spec.chapters) == 2
    assert spec.chapters[0].title == CHAPTER_SCREENING
    assert spec.chapters[1].title == CHAPTER_INTERVIEW


def test_safe_filename_sanitizes_slashes():
    assert safe_filename("A/B\\C") == "A_B_C_interview_design.pdf"
    assert safe_filename("") == "export_interview_design.pdf"
