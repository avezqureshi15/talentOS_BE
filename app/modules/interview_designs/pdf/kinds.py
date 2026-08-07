from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExportKind = Literal["all", "screening", "interview", "review"]
EXPORT_KIND_VALUES: tuple[ExportKind, ...] = ("all", "screening", "interview", "review")


@dataclass(frozen=True)
class ChapterDef:
    kind: Literal["screening", "interview", "review"]
    title: str
    sections_attr: str
    filename_suffix: str


EXPORT_CHAPTERS: tuple[ChapterDef, ...] = (
    ChapterDef("screening", "AI Screening Questions", "screening_sections", "ai_screening"),
    ChapterDef("interview", "AI Interview Questions", "interview_sections", "ai_interview"),
    ChapterDef("review", "Candidate Review Questions", "review_sections", "candidate_review"),
)

ALL_FILENAME_SUFFIX = "interview_design"


def resolve_chapters(kind: ExportKind) -> tuple[ChapterDef, ...]:
    if kind == "all":
        return EXPORT_CHAPTERS
    for chapter in EXPORT_CHAPTERS:
        if chapter.kind == kind:
            return (chapter,)
    raise ValueError(f"Unknown export kind: {kind}")


def filename_suffix_for_kind(kind: ExportKind) -> str:
    if kind == "all":
        return ALL_FILENAME_SUFFIX
    chapters = resolve_chapters(kind)
    return chapters[0].filename_suffix
