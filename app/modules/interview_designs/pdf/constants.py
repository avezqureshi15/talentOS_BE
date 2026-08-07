from app.modules.interview_designs.pdf.kinds import (
    ALL_FILENAME_SUFFIX,
    EXPORT_CHAPTERS,
)

DOC_SUBTITLE = "Interview Design"
EMPTY_CHAPTER_SUMMARY = "0 sections · 0 min"

# Back-compat aliases used by older tests / imports
FILENAME_SUFFIX = ALL_FILENAME_SUFFIX
CHAPTER_SCREENING = EXPORT_CHAPTERS[0].title
CHAPTER_INTERVIEW = EXPORT_CHAPTERS[1].title
CHAPTER_REVIEW = EXPORT_CHAPTERS[2].title
