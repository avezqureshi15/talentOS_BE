from dataclasses import dataclass

from app.core.constants import PipelineStage
from app.modules.evaluations.evaluation_model import Candidate

CANDIDATE_COLUMNS: list[tuple[str, str]] = [
    ("name", "Name"),
    ("email", "Email"),
    ("phone", "Phone"),
    ("status", "Status"),
    ("stage", "Stage"),
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

_MID_PIPELINE_STAGES = {
    PipelineStage.SCREENING.value,
    PipelineStage.INTERVIEW.value,
    PipelineStage.WAITING_FOR_EVALUATION.value,
    PipelineStage.EVALUATED.value,
}


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
]


def resolve_stage_sheet_key(candidate: Candidate) -> str:
    """Map a candidate to exactly one stage sheet key (exclusive placement)."""
    if candidate.final_verdict == "SELECTED" or candidate.stage == PipelineStage.SELECTED.value:
        return PipelineStage.SELECTED.value
    if candidate.final_verdict == "REJECTED" or candidate.stage == PipelineStage.REJECTED.value:
        return PipelineStage.REJECTED.value
    if candidate.stage in _MID_PIPELINE_STAGES:
        return candidate.stage  # type: ignore[return-value]
    return PipelineStage.RESUME_SHORTLISTING.value
