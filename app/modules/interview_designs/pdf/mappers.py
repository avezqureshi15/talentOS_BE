from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.common.pdf.models import (
    ChapterSpec,
    ContentItemSpec,
    ContentSectionSpec,
    DocumentSpec,
)
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.interview_designs.pdf.constants import (
    CHAPTER_INTERVIEW,
    CHAPTER_SCREENING,
    DOC_SUBTITLE,
    EMPTY_CHAPTER_SUMMARY,
)


def _section_minutes(section: dict[str, Any]) -> float:
    total = 0.0
    for q in section.get("questions") or []:
        try:
            total += float(q.get("timeAllocationMinutes") or 0)
        except (TypeError, ValueError):
            continue
    return total


def _format_minutes(minutes: float) -> str:
    if minutes == int(minutes):
        return f"{int(minutes)} min"
    return f"{minutes:g} min"


def _chapter_summary(sections: list[dict[str, Any]]) -> str:
    if not sections:
        return EMPTY_CHAPTER_SUMMARY
    total_min = sum(_section_minutes(s) for s in sections)
    return f"{len(sections)} sections · {_format_minutes(total_min)}"


def _map_question(question: dict[str, Any]) -> ContentItemSpec:
    minutes = question.get("timeAllocationMinutes")
    score = question.get("score")
    detail_parts: list[str] = []
    if minutes is not None and minutes != "":
        try:
            detail_parts.append(_format_minutes(float(minutes)))
        except (TypeError, ValueError):
            pass
    if score is not None and score != "":
        detail_parts.append(f"score {score}")
    bullets = [str(p) for p in (question.get("expected_points") or []) if p]
    return ContentItemSpec(
        text=str(question.get("question") or "").strip() or "(untitled question)",
        detail=" · ".join(detail_parts),
        bullets=bullets,
    )


def _map_section(section: dict[str, Any], index: int) -> ContentSectionSpec:
    questions = section.get("questions") or []
    minutes = _section_minutes(section)
    depth = section.get("depth") or ""
    meta_parts = [_format_minutes(minutes)]
    if depth:
        meta_parts.append(f"Depth: {depth}")
    type_label = str(section.get("type") or "").strip()
    title = str(section.get("title") or "").strip() or f"Section {index}"
    heading = f"{index:02d}. {title}"
    return ContentSectionSpec(
        eyebrow=type_label,
        heading=heading,
        description=str(section.get("description") or "").strip(),
        meta_line=" · ".join(meta_parts),
        items=[_map_question(q) for q in questions if isinstance(q, dict)],
    )


def map_sections_to_chapter(title: str, sections: list[dict[str, Any]] | None) -> ChapterSpec:
    safe_sections = [s for s in (sections or []) if isinstance(s, dict)]
    return ChapterSpec(
        title=title,
        summary=_chapter_summary(safe_sections),
        sections=[_map_section(s, i) for i, s in enumerate(safe_sections, start=1)],
    )


def build_document_spec(
    hiring_request: HiringRequest,
    screening_sections: list[dict[str, Any]] | None,
    interview_sections: list[dict[str, Any]] | None,
    *,
    generated_at: datetime | None = None,
) -> DocumentSpec:
    generated = generated_at or datetime.now(timezone.utc)
    meta: list[tuple[str, str]] = []
    if hiring_request.department:
        meta.append(("Department", str(hiring_request.department)))
    if hiring_request.location:
        meta.append(("Location", str(hiring_request.location)))
    if hiring_request.type:
        meta.append(("Type", str(hiring_request.type)))
    meta.append(("Generated", generated.strftime("%Y-%m-%d %H:%M UTC")))

    return DocumentSpec(
        title=str(hiring_request.title or "Untitled hiring request"),
        subtitle=DOC_SUBTITLE,
        meta=meta,
        chapters=[
            map_sections_to_chapter(CHAPTER_SCREENING, screening_sections),
            map_sections_to_chapter(CHAPTER_INTERVIEW, interview_sections),
        ],
    )


def safe_filename(title: str) -> str:
    from app.modules.interview_designs.pdf.constants import FILENAME_SUFFIX

    cleaned = str(title or "export").replace("/", "_").replace("\\", "_").strip()
    cleaned = cleaned or "export"
    return f"{cleaned}_{FILENAME_SUFFIX}.pdf"
