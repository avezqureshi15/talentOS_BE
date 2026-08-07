from __future__ import annotations

from xml.sax.saxutils import escape

from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.common.pdf.models import ChapterSpec, ContentItemSpec, ContentSectionSpec, DocumentSpec
from app.common.pdf.styles import COLOR_RULE, build_styles


def _p(text: str, style_name: str, styles: dict) -> Paragraph:
    return Paragraph(escape(text or ""), styles[style_name])


def build_title_block(spec: DocumentSpec, styles: dict) -> list:
    flowables: list = [
        _p("TalentOS", "brand", styles),
        _p(spec.title or "Untitled", "title", styles),
    ]
    if spec.subtitle:
        flowables.append(_p(spec.subtitle, "subtitle", styles))
    return flowables


def build_meta_table(meta: list[tuple[str, str]], styles: dict) -> list:
    if not meta:
        return []
    rows = [
        [_p(label, "meta_label", styles), _p(value, "meta_value", styles)]
        for label, value in meta
        if value
    ]
    if not rows:
        return []
    table = Table(rows, colWidths=[90, 380])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, COLOR_RULE),
            ]
        )
    )
    return [table, Spacer(1, 12)]


def _build_item(item: ContentItemSpec, index: int, styles: dict) -> list:
    """Keep a single question + its meta/bullets together; allow page breaks between questions."""
    parts: list = [_p(f"{index}. {item.text}", "item", styles)]
    if item.detail:
        parts.append(_p(item.detail, "item_detail", styles))
    for bullet in item.bullets:
        if bullet:
            parts.append(_p(f"• {bullet}", "bullet", styles))
    return [KeepTogether(parts)]


def _build_section_header(section: ContentSectionSpec, styles: dict) -> list:
    """Keep section chrome together so title/description are not orphaned across a page break."""
    header: list = []
    if section.eyebrow:
        header.append(_p(section.eyebrow, "section_eyebrow", styles))
    if section.heading:
        header.append(_p(section.heading, "section_heading", styles))
    if section.description:
        header.append(_p(section.description, "section_desc", styles))
    if section.meta_line:
        header.append(_p(section.meta_line, "section_meta", styles))
    if not header:
        return []
    return [KeepTogether(header)]


def _build_section(section: ContentSectionSpec, styles: dict) -> list:
    """Flow section content across pages: header stays intact, questions wrap individually."""
    flowables: list = []
    flowables.extend(_build_section_header(section, styles))
    if not section.items:
        flowables.append(_p("No questions in this section.", "empty", styles))
        return flowables
    for i, item in enumerate(section.items, start=1):
        flowables.extend(_build_item(item, i, styles))
    return flowables


def build_chapter(chapter: ChapterSpec, styles: dict) -> list:
    heading: list = [_p(chapter.title, "chapter", styles)]
    if chapter.summary:
        heading.append(_p(chapter.summary, "chapter_summary", styles))
    flowables: list = [KeepTogether(heading)]
    if not chapter.sections:
        flowables.append(_p("No sections.", "empty", styles))
        return flowables
    for section in chapter.sections:
        flowables.extend(_build_section(section, styles))
    return flowables


def build_document_flowables(spec: DocumentSpec) -> list:
    styles = build_styles()
    flowables: list = []
    flowables.extend(build_title_block(spec, styles))
    flowables.extend(build_meta_table(list(spec.meta), styles))
    for chapter in spec.chapters:
        flowables.extend(build_chapter(chapter, styles))
    if spec.footer_note:
        flowables.append(Spacer(1, 16))
        flowables.append(_p(spec.footer_note, "footer", styles))
    return flowables
