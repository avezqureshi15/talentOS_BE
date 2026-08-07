import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.hiring_requests.ai_integration_router import (
    MoveToAiInterviewRequest,
    move_to_ai_interview,
)
from app.modules.rounds.round_model import Round


def _build_context():
    hr_id = "b7590364-0000-0000-0000-000000000000"
    cand_id = 123
    hr = SimpleNamespace(id=hr_id, title="Backend Engineer", rh_external_job_id=None)
    candidate = SimpleNamespace(
        id=cand_id,
        candidate_name="Ada",
        candidate_email="ada@example.com",
        candidate_phone="+911234567890",
        rh_external_candidate_id=None,
        current_round_id=None,
        status="MOVE_TO_NEXT_ROUND",
        stage="MOVE_TO_NEXT_ROUND",
    )

    session = MagicMock()
    hr_query = MagicMock()
    hr_query.filter.return_value.first.return_value = hr
    cand_query = MagicMock()
    cand_query.filter.return_value.first.return_value = candidate
    session.query.side_effect = [hr_query, cand_query]

    captured: list[object] = []

    def fake_add(obj: object) -> None:
        captured.append(obj)

    def fake_flush() -> None:
        for obj in captured:
            if isinstance(obj, Round) and obj.id is None:
                obj.id = uuid.uuid4()

    session.add.side_effect = fake_add
    session.flush.side_effect = fake_flush

    client = MagicMock()
    client.create_candidate_with_interview = AsyncMock(return_value={
        "candidate": {"id": "poc-cand-1", "job_id": "poc-job-1"},
        "interview": {
            "id": "poc-int-1",
            "interview_url": "https://poc.example/interview/tok1",
            "status": "pending",
        },
    })

    return hr_id, cand_id, hr, candidate, session, client, captured


def test_move_to_interview_sets_status_and_stage():
    hr_id, cand_id, hr, candidate, session, client, captured = _build_context()

    with patch(
        "app.modules.hiring_requests.ai_integration_router.AiRecruitmentClient",
        return_value=client,
    ):
        with patch(
            "app.modules.hiring_requests.ai_integration_router.EventService"
        ) as mock_event_svc:
            with patch(
                "app.modules.hiring_requests.ai_integration_router.send_interview_invite_email",
                return_value=False,
            ):
                result = asyncio.run(
                    move_to_ai_interview(
                        hr_id,
                        cand_id,
                        MoveToAiInterviewRequest(
                            round_name="AI Interview Round",
                            round_type="AI_INTERVIEW_ROUND",
                        ),
                        session,
                    )
                )

    round_obj = next(obj for obj in captured if isinstance(obj, Round))

    assert result["status"] == "created"
    assert result["rh_external_session_id"] == "poc-int-1"
    assert candidate.status == "INTERVIEW_SCHEDULED"
    assert candidate.stage == "AI_INTERVIEW"
    assert candidate.current_round_id == round_obj.id
    assert candidate.rh_external_candidate_id == "poc-cand-1"
    assert round_obj.round_type == "AI_INTERVIEW_ROUND"
    assert round_obj.name == "AI Interview Round"
    assert round_obj.rh_external_session_id == "poc-int-1"
    assert round_obj.rh_unique_token == "tok1"
    assert hr.rh_external_job_id == "poc-job-1"

    reviews = [obj for obj in captured if type(obj).__name__ == "Review"]
    assert len(reviews) == 1
    assert reviews[0].entity_type == "ai_interview"
    assert reviews[0].reviews["status"] == "pending"

    events = mock_event_svc.return_value.create_event.call_args_list
    assert any(
        call.args[0].state_code == "INTERVIEW_SCHEDULED"
        and call.args[0].event_metadata["stage"] == "AI_INTERVIEW"
        for call in events
    )


def test_move_to_interview_rolls_back_and_raises_502_when_poc_fails():
    hr_id, cand_id, hr, candidate, session, client, captured = _build_context()
    client.create_candidate_with_interview = AsyncMock(return_value=None)

    with (
        patch(
            "app.modules.hiring_requests.ai_integration_router.AiRecruitmentClient",
            return_value=client,
        ),
        patch(
            "app.modules.hiring_requests.ai_integration_router.EventService"
        ),
        patch(
            "app.modules.hiring_requests.ai_integration_router.send_interview_invite_email",
            return_value=False,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                move_to_ai_interview(
                    hr_id,
                    cand_id,
                    MoveToAiInterviewRequest(round_name="AI Interview Round"),
                    session,
                )
            )

    assert exc_info.value.status_code == 502
    session.rollback.assert_called_once()
    assert candidate.status == "MOVE_TO_NEXT_ROUND"
    assert candidate.stage == "MOVE_TO_NEXT_ROUND"