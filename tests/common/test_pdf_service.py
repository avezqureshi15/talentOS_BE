from app.common.pdf import (
    ChapterSpec,
    ContentItemSpec,
    ContentSectionSpec,
    DocumentSpec,
    PdfService,
)
from app.common.pdf.builders import build_document_flowables
from reportlab.platypus import KeepTogether


def test_pdf_service_renders_valid_pdf():
    spec = DocumentSpec(
        title="Sample Role",
        subtitle="Interview Design",
        meta=[("Department", "Engineering"), ("Location", "Remote")],
        chapters=[
            ChapterSpec(
                title="AI Screening Questions",
                summary="1 sections · 1 min",
                sections=[
                    ContentSectionSpec(
                        eyebrow="Q&A",
                        heading="01. Availability",
                        description="Checks notice period.",
                        meta_line="1 min · Depth: Standard",
                        items=[
                            ContentItemSpec(
                                text="When can you start?",
                                detail="1 min · score 5",
                                bullets=["Look for clear timeline"],
                            )
                        ],
                    )
                ],
            ),
            ChapterSpec(title="AI Interview Questions", summary="0 sections · 0 min", sections=[]),
        ],
    )
    buf = PdfService().render(spec)
    data = buf.getvalue()
    assert data.startswith(b"%PDF")
    assert len(data) > 200


def test_section_flowables_do_not_wrap_entire_section_in_one_keep_together():
    """Large KeepTogether blocks cause empty page bottoms; only headers/items stay atomic."""
    spec = DocumentSpec(
        title="Role",
        chapters=[
            ChapterSpec(
                title="Chapter",
                sections=[
                    ContentSectionSpec(
                        eyebrow="Q&A",
                        heading="01. Big section",
                        description="Desc",
                        meta_line="10 min",
                        items=[
                            ContentItemSpec(text=f"Question {i}", detail="1 min", bullets=["a", "b"])
                            for i in range(1, 8)
                        ],
                    )
                ],
            )
        ],
    )
    flowables = build_document_flowables(spec)
    keep_togethers = [f for f in flowables if isinstance(f, KeepTogether)]
    # One chapter heading + one section header + one per question (7) — not a single mega-block.
    assert len(keep_togethers) >= 9
    max_inner = max(len(kt._content) for kt in keep_togethers)
    # A whole section with 7 questions would be far larger; header/items stay small.
    assert max_inner <= 6
