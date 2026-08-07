from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch

PAGE_MARGIN = 0.75 * inch
BRAND_NAME = "TalentOS"

COLOR_TEXT = colors.HexColor("#1a1a1a")
COLOR_MUTED = colors.HexColor("#5c5c5c")
COLOR_RULE = colors.HexColor("#d0d0d0")
COLOR_CHAPTER = colors.HexColor("#0f172a")


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "PdfBrand",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=COLOR_MUTED,
            spaceAfter=4,
        ),
        "title": ParagraphStyle(
            "PdfTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=COLOR_TEXT,
            spaceAfter=6,
            leading=22,
        ),
        "subtitle": ParagraphStyle(
            "PdfSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            textColor=COLOR_MUTED,
            spaceAfter=12,
        ),
        "meta_label": ParagraphStyle(
            "PdfMetaLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=COLOR_MUTED,
        ),
        "meta_value": ParagraphStyle(
            "PdfMetaValue",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=COLOR_TEXT,
        ),
        "chapter": ParagraphStyle(
            "PdfChapter",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=COLOR_CHAPTER,
            spaceBefore=18,
            spaceAfter=4,
            leading=18,
        ),
        "chapter_summary": ParagraphStyle(
            "PdfChapterSummary",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=COLOR_MUTED,
            spaceAfter=10,
        ),
        "section_eyebrow": ParagraphStyle(
            "PdfSectionEyebrow",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=COLOR_MUTED,
            spaceBefore=12,
            spaceAfter=2,
        ),
        "section_heading": ParagraphStyle(
            "PdfSectionHeading",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=COLOR_TEXT,
            spaceAfter=3,
            leading=14,
        ),
        "section_desc": ParagraphStyle(
            "PdfSectionDesc",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=COLOR_MUTED,
            spaceAfter=4,
            leading=12,
            alignment=TA_LEFT,
        ),
        "section_meta": ParagraphStyle(
            "PdfSectionMeta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=COLOR_MUTED,
            spaceAfter=6,
        ),
        "item": ParagraphStyle(
            "PdfItem",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=COLOR_TEXT,
            spaceBefore=4,
            spaceAfter=1,
            leading=12,
            leftIndent=12,
        ),
        "item_detail": ParagraphStyle(
            "PdfItemDetail",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=COLOR_MUTED,
            spaceAfter=2,
            leftIndent=12,
        ),
        "bullet": ParagraphStyle(
            "PdfBullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=COLOR_MUTED,
            leftIndent=28,
            bulletIndent=16,
            spaceAfter=1,
            leading=11,
        ),
        "empty": ParagraphStyle(
            "PdfEmpty",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=COLOR_MUTED,
            spaceAfter=8,
        ),
        "footer": ParagraphStyle(
            "PdfFooter",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=COLOR_MUTED,
        ),
    }
