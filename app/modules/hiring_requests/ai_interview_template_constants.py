"""Constants for the POC-flat -> FE template shape mapping.

Kept separate from the mapper so tests can pin behavior and product tuning
(thresholds, labels, keyword sets) does not touch mapping logic.
"""

from __future__ import annotations

MAX_RATING = 5.0
TOTAL_CRITERIA = 5

# Score thresholds (on a 0..MAX_RATING scale)
BELOW_BAR_LT = 2.5
MEETS_BAR_LT = 4.0
CRITERIA_MET_GTE = 3.5

# POC `final_recommendation` -> template `aiRecommendation` enum
VERDICT_MAP: dict[str, str] = {
    "shortlisted": "ADVANCE",
    "pass": "ADVANCE",
    "selected": "ADVANCE",
    "advance": "ADVANCE",
    "rejected": "REJECT",
    "fail": "REJECT",
    "reject": "REJECT",
    "needs_review": "POTENTIAL_FIT",
    "potential_fit": "POTENTIAL_FIT",
}
DEFAULT_VERDICT = "POTENTIAL_FIT"

# The five POC dimensions -> template topic titles + keyword sets used
# to slice flat strengths[]/weaknesses[] into per-topic bullets.
DIMENSIONS: list[dict] = [
    {
        "key": "technical_fit_score",
        "id": "technical_fit",
        "title": "Technical Fit",
        "keywords": ("technical", "engineering", "code", "coding", "architecture",
                     "system", "framework", "language", "algorithm", "stack",
                     "design pattern", "database", "api"),
    },
    {
        "key": "communication_score",
        "id": "communication",
        "title": "Communication",
        "keywords": ("communicat", "articulat", "explain", "clarity",
                     "listen", "verbal", "concise", "response"),
    },
    {
        "key": "problem_solving_score",
        "id": "problem_solving",
        "title": "Problem Solving",
        "keywords": ("problem", "solv", "reason", "analytic", "approach",
                     "debug", "troubleshoot", "logic"),
    },
    {
        "key": "experience_score",
        "id": "experience",
        "title": "Experience",
        "keywords": ("experience", "background", "worked", "history",
                     "project", "prior", "past", "years", "role"),
    },
    {
        "key": "role_alignment_score",
        "id": "role_alignment",
        "title": "Role Alignment",
        "keywords": ("role", "fit", "align", "responsibilit", "expectation",
                     "position", "requirement", "match"),
    },
]

DEFAULT_SUBCRITERIA_TITLE = "Overall assessment"
DEFAULT_TRANSCRIPT_SECTION_TITLE = "Interview"

# Regex prefixes used to attribute speaker in a raw transcript string.
INTERVIEWER_PREFIXES = ("interviewer:", "assistant:", "ai:", "bot:", "recruiter:")
CANDIDATE_PREFIXES = ("candidate:", "user:", "you:")
