from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContentItemSpec:
    text: str
    detail: str = ""
    bullets: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContentSectionSpec:
    eyebrow: str = ""
    heading: str = ""
    description: str = ""
    meta_line: str = ""
    items: list[ContentItemSpec] = field(default_factory=list)


@dataclass(frozen=True)
class ChapterSpec:
    title: str
    summary: str = ""
    sections: list[ContentSectionSpec] = field(default_factory=list)


@dataclass(frozen=True)
class DocumentSpec:
    title: str
    subtitle: str = ""
    meta: list[tuple[str, str]] = field(default_factory=list)
    chapters: list[ChapterSpec] = field(default_factory=list)
    footer_note: str = ""
