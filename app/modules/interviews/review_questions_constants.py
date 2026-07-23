"""Static fallback review questions when interview.review_questions is empty."""

from app.common.schemas.review_questions import ReviewPhase

STATIC_REVIEW_QUESTIONS_SOURCE = "static"

STATIC_REVIEW_PHASES: list[ReviewPhase] = [
    ReviewPhase(
        phase="Overall",
        questions=[
            "Communication",
            "Technical Skills",
            "Problem Solving",
            "Cultural Fit",
        ],
    ),
]
