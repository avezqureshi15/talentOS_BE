from dataclasses import dataclass


@dataclass
class StateTransition:
    set_final_verdict: str | None = None
    set_status: str | None = None


TRANSITIONS: dict[str, StateTransition] = {
    "hr.shortlisted": StateTransition(
        set_status="MOVE_TO_NEXT_ROUND",
    ),
    "hr.rejected": StateTransition(
        set_final_verdict="REJECTED",
        set_status="MOVED_OUT_OF_HIRING_PIPELINE",
    ),
    "final.selection.SELECTED": StateTransition(
        set_final_verdict="SELECTED",
        set_status="MOVED_OUT_OF_HIRING_PIPELINE",
    ),
    "final.selection.REJECTED": StateTransition(
        set_final_verdict="REJECTED",
        set_status="REJECTED",
    ),
}
