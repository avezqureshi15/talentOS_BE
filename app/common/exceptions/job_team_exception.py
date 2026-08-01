from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class JobTeamMemberNotFoundException(BaseAppException):
    def __init__(self, user_id: int):
        super().__init__(
            message=f"User {user_id} is not a member of this job team",
            code=ErrorCode.JOB_TEAM_MEMBER_NOT_FOUND,
            status_code=404,
        )


class JobTeamAlreadyMemberException(BaseAppException):
    def __init__(self, user_id: int):
        super().__init__(
            message=f"User {user_id} is already a member of this job team",
            code=ErrorCode.JOB_TEAM_ALREADY_MEMBER,
            status_code=409,
        )
