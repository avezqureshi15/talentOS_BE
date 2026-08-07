from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.modules.interview_designs.pdf.constants import (
    CHAPTER_INTERVIEW,
    CHAPTER_REVIEW,
    CHAPTER_SCREENING,
)
from app.modules.interview_designs.pdf.kinds import resolve_chapters
from app.modules.interview_designs.pdf.mappers import (
    build_document_spec,
    map_sections_to_chapter,
    safe_filename,
)


def _hr():
    return SimpleNamespace(
        title="Senior Golang Developer",
        department="Engineering",
        location="Bangalore",
        type="Full-time",
    )


def _design(**overrides):
    base = SimpleNamespace(
        screening_sections=[],
        interview_sections=[{"id": "s", "title": "Tech", "type": "Q&A", "questions": []}],
        review_sections=[{"id": "r", "title": "Review", "type": "Q&A", "questions": []}],
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


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


def test_build_document_spec_all_includes_three_chapters():
    generated = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    spec = build_document_spec(_hr(), _design(), kind="all", generated_at=generated)
    assert spec.title == "Senior Golang Developer"
    assert spec.subtitle == "Interview Design"
    assert ("Department", "Engineering") in spec.meta
    assert ("Generated", "2026-08-07 12:00 UTC") in spec.meta
    assert len(spec.chapters) == 3
    assert [c.title for c in spec.chapters] == [
        CHAPTER_SCREENING,
        CHAPTER_INTERVIEW,
        CHAPTER_REVIEW,
    ]


@pytest.mark.parametrize(
    "kind,expected_title",
    [
        ("screening", CHAPTER_SCREENING),
        ("interview", CHAPTER_INTERVIEW),
        ("review", CHAPTER_REVIEW),
    ],
)
def test_build_document_spec_single_kind(kind, expected_title):
    spec = build_document_spec(_hr(), _design(), kind=kind)
    assert len(spec.chapters) == 1
    assert spec.chapters[0].title == expected_title


def test_safe_filename_per_kind():
    assert safe_filename("A/B\\C", "all") == "A_B_C_interview_design.pdf"
    assert safe_filename("", "all") == "export_interview_design.pdf"
    assert safe_filename("Role", "screening") == "Role_ai_screening.pdf"
    assert safe_filename("Role", "interview") == "Role_ai_interview.pdf"
    assert safe_filename("Role", "review") == "Role_candidate_review.pdf"


def test_resolve_chapters_unknown_kind_raises():
    with pytest.raises(ValueError):
        resolve_chapters("unknown")  # type: ignore[arg-type]
