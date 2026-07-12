from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class ApplicationNotFoundException(BaseAppException):
    def __init__(self, application_id: int):
        super().__init__(
            message=f"Application with id {application_id} not found",
            code=ErrorCode.APPLICATION_NOT_FOUND,
            status_code=404,
        )


class CandidateFinalizedException(BaseAppException):
    def __init__(self, candidate_id: int, existing_verdict: str):
        super().__init__(
            message=f"Candidate {candidate_id} is already finalized with verdict '{existing_verdict}'. No further changes allowed.",
            code=ErrorCode.CANDIDATE_FINALIZED,
            status_code=400,
        )
