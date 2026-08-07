from dataclasses import dataclass

from app.core.constants import EvaluationStatus, PipelineStage
from app.modules.evaluations.evaluation_model import Candidate

CANDIDATE_COLUMNS: list[tuple[str, str]] = [
    ("name", "Name"),
    ("email", "Email"),
    ("phone", "Phone"),
    ("status", "Status"),
    ("stage", "Stage"),
    ("archived", "Archived"),
    ("fit_score", "Fit Score"),
    ("review_verdict", "Review Verdict"),
    ("final_verdict", "Final Verdict"),
    ("disqualified_by", "Disqualified By"),
    ("current_ctc", "Current CTC"),
    ("expected_ctc", "Expected CTC"),
    ("years_of_experience", "YOE"),
    ("location", "Location"),
    ("notice_period", "Notice Period"),
    ("willing_to_relocate", "Willing to Relocate"),
    ("linkedin_url", "LinkedIn"),
    ("resume_url", "Resume URL"),
    ("applied_at", "Applied At"),
]

ALL_CANDIDATES_SHEET_TITLE = "All Candidates"
HIRING_REQUEST_SHEET_TITLE = "Hiring Request"
ARCHIVED_SHEET_KEY = "ARCHIVED"
ON_HOLD_SHEET_KEY = "ON_HOLD"

# Mirrors FE STAGE_FILTER_MAP / BE STAGE_QUERY_MAP (status-aware pipeline tabs).
_RESUME_STAGES = frozenset({
    PipelineStage.RESUME_SHORTLISTING.value,
    PipelineStage.RESUME_SHORTLISTED.value,
})
_SCREENING_STAGES = frozenset({
    PipelineStage.SCREENING.value,
    "AI_SCREENING",
    PipelineStage.MOVE_TO_NEXT_ROUND.value,
})
_INTERVIEW_STAGES = frozenset({
    PipelineStage.INTERVIEW.value,
    "AI_INTERVIEW",
})
_INTERVIEW_STATUSES = frozenset({
    EvaluationStatus.INTERVIEW_SCHEDULED.value,
    EvaluationStatus.INTERVIEW_RESCHEDULED.value,
    EvaluationStatus.INTERVIEW_CANCELLED.value,
})
_EVALUATED_STATUSES = frozenset({
    EvaluationStatus.UNDER_EVALUATION.value,
})


@dataclass(frozen=True)
class StageSheetDef:
    key: str
    title: str


# Display order for workbook sheets (after Hiring Request + All Candidates).
STAGE_SHEETS: list[StageSheetDef] = [
    StageSheetDef(PipelineStage.RESUME_SHORTLISTING.value, "Resume Shortlisting"),
    StageSheetDef(PipelineStage.SCREENING.value, "Screening"),
    StageSheetDef(PipelineStage.INTERVIEW.value, "Interview"),
    StageSheetDef(PipelineStage.WAITING_FOR_EVALUATION.value, "Waiting for Evaluation"),
    StageSheetDef(PipelineStage.EVALUATED.value, "Evaluated"),
    StageSheetDef(PipelineStage.SELECTED.value, "Selected"),
    StageSheetDef(PipelineStage.REJECTED.value, "Rejected"),
    StageSheetDef(ON_HOLD_SHEET_KEY, "On Hold"),
    StageSheetDef(ARCHIVED_SHEET_KEY, "Archived"),
]


def resolve_stage_sheet_key(candidate: Candidate) -> str:
    """Map a candidate to exactly one sheet key (exclusive placement).

    Rules mirror pipeline tab filters:
    - Archived → Archived sheet only (not also in a stage sheet)
    - Final verdict / decision board outcomes take priority
    - Interview vs Evaluated is status-aware (AI + regular)
    - AI_SCREENING / AI_INTERVIEW are included with their regular counterparts
    """
    if bool(candidate.archived):
        return ARCHIVED_SHEET_KEY

    final_verdict = (candidate.final_verdict or "").upper()
    stage = candidate.stage or ""
    status = candidate.status or ""

    if final_verdict == "SELECTED" or stage == PipelineStage.SELECTED.value:
        return PipelineStage.SELECTED.value
    if final_verdict == "REJECTED" or stage == PipelineStage.REJECTED.value:
        return PipelineStage.REJECTED.value
    if final_verdict == "ON_HOLD":
        return ON_HOLD_SHEET_KEY

    if (
        stage == PipelineStage.WAITING_FOR_EVALUATION.value
        or status == EvaluationStatus.WAITING_FOR_REVIEW.value
    ):
        return PipelineStage.WAITING_FOR_EVALUATION.value

    if stage in _INTERVIEW_STAGES and status in _EVALUATED_STATUSES:
        return PipelineStage.EVALUATED.value

    if stage in _INTERVIEW_STAGES and status in _INTERVIEW_STATUSES:
        return PipelineStage.INTERVIEW.value

    if stage in _INTERVIEW_STAGES:
        return PipelineStage.INTERVIEW.value

    if stage == PipelineStage.EVALUATED.value:
        return PipelineStage.EVALUATED.value

    if stage in _SCREENING_STAGES:
        return PipelineStage.SCREENING.value

    if stage in _RESUME_STAGES:
        return PipelineStage.RESUME_SHORTLISTING.value

    return PipelineStage.RESUME_SHORTLISTING.value
