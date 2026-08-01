import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.ai_recruitment_client import AiRecruitmentClient
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.interview_designs.interview_design_model import InterviewDesign
from app.modules.interview_designs.interview_design_schema import (
    InterviewDesignResponse,
    InterviewDesignUpdate,
)

_DEFAULT_SECTION_ID = "section-1"
_DEFAULT_SECTION_TITLE = "Q&A"
_DEFAULT_SECTION_TYPE = "Q&A"
_DEFAULT_SECTION_DEPTH = "Standard"
_DEFAULT_INTERVIEW_MINUTES = 5
_DEFAULT_SCREENING_MINUTES = 1
_DEFAULT_QUESTION_SCORE = 5
_POC_SYNC_ERROR = "ai-recruitment-poc unreachable — design saved as draft"
_POC_JOB_CREATE_ERROR = "Failed to create linked job in ai-recruitment-poc"
_DEFAULT_SCREENING_QUESTIONS: list[dict] = [
    {
        "id": "screening-default-availability",
        "question": "When are you available to start a new role? Are you currently looking actively?",
    },
    {
        "id": "screening-default-employment",
        "question": "Are you currently employed? What is your current role and company?",
    },
    {
        "id": "screening-default-experience",
        "question": "Can you briefly describe your most relevant experience for this role?",
    },
    {
        "id": "screening-default-current-ctc",
        "question": "What is your current compensation package (annual CTC)?",
    },
    {
        "id": "screening-default-expected-ctc",
        "question": "What are your salary expectations for this role?",
    },
    {
        "id": "screening-default-notice",
        "question": "What is your notice period at your current company?",
    },
    {
        "id": "screening-default-location",
        "question": "What is your remote, hybrid, or on-site preference?",
    },
    {
        "id": "screening-default-interest",
        "question": "Are you interested in moving forward with this opportunity?",
    },
]


def _build_seed_section(questions: list[dict], default_minutes: int) -> list[dict]:
    return [
        {
            "id": _DEFAULT_SECTION_ID,
            "title": _DEFAULT_SECTION_TITLE,
            "type": _DEFAULT_SECTION_TYPE,
            "description": "",
            "depth": _DEFAULT_SECTION_DEPTH,
            "questions": [
                {
                    "id": q.get("id") or str(uuid.uuid4()),
                    "question": q.get("question") or "",
                    "score": q.get("score") if q.get("score") is not None else _DEFAULT_QUESTION_SCORE,
                    "timeAllocationMinutes": default_minutes,
                }
                for q in questions
            ],
        }
    ]


def _flatten_sections(sections: list[dict]) -> list[dict]:
    return [
        {"id": q["id"], "question": q["question"], "score": q["score"]}
        for section in sections
        for q in section.get("questions", [])
    ]


def _to_response(
    hiring_request_id: uuid.UUID,
    design: InterviewDesign,
    sync_status: str = "synced",
    sync_errors: list[str] | None = None,
) -> InterviewDesignResponse:
    return InterviewDesignResponse(
        hiring_request_id=hiring_request_id,
        screening_sections=design.screening_sections or [],
        interview_sections=design.interview_sections or [],
        updated_at=design.updated_at,
        sync_status=sync_status,
        sync_errors=sync_errors or [],
    )


async def _resolve_rh_job(hiring_request: HiringRequest, db: Session) -> str:
    if hiring_request.rh_external_job_id:
        return hiring_request.rh_external_job_id

    client = AiRecruitmentClient()
    created = await client.create_job(
        title=hiring_request.title,
        description=hiring_request.description,
        required_skills=hiring_request.requirements,
        location=hiring_request.location,
        department=hiring_request.department,
        employment_type=hiring_request.type,
    )
    if not created:
        raise HTTPException(status_code=502, detail=_POC_JOB_CREATE_ERROR)

    hiring_request.rh_external_job_id = created["id"]
    db.commit()
    return created["id"]


async def get_or_seed_design(hiring_request_id: str, db: Session) -> InterviewDesignResponse:
    hiring_request = db.query(HiringRequest).filter(HiringRequest.id == hiring_request_id).first()
    if not hiring_request:
        raise HTTPException(status_code=404, detail="Hiring request not found")

    design = (
        db.query(InterviewDesign)
        .filter(InterviewDesign.hiring_request_id == hiring_request.id)
        .first()
    )
    if design:
        return _to_response(hiring_request.id, design)

    screening_sections = _build_seed_section(
        _DEFAULT_SCREENING_QUESTIONS,
        _DEFAULT_SCREENING_MINUTES,
    )
    interview_sections: list[dict] = []
    if hiring_request.rh_external_job_id:
        client = AiRecruitmentClient()
        result = await client.get_job_questions(
            hiring_request.rh_external_job_id,
            external_job_id=str(hiring_request.id),
        )
        if result:
            screening_sections = _build_seed_section(
                result.get("screening_questions") or _DEFAULT_SCREENING_QUESTIONS,
                _DEFAULT_SCREENING_MINUTES,
            )
            interview_sections = _build_seed_section(
                result.get("interview_questions") or [],
                _DEFAULT_INTERVIEW_MINUTES,
            )

    design = InterviewDesign(
        hiring_request_id=hiring_request.id,
        screening_sections=screening_sections,
        interview_sections=interview_sections,
    )
    db.add(design)
    db.commit()
    db.refresh(design)
    return _to_response(hiring_request.id, design)


async def update_design(
    hiring_request_id: str,
    body: InterviewDesignUpdate,
    db: Session,
) -> InterviewDesignResponse:
    hiring_request = db.query(HiringRequest).filter(HiringRequest.id == hiring_request_id).first()
    if not hiring_request:
        raise HTTPException(status_code=404, detail="Hiring request not found")

    design = (
        db.query(InterviewDesign)
        .filter(InterviewDesign.hiring_request_id == hiring_request.id)
        .first()
    )
    if design is None:
        design = InterviewDesign(hiring_request_id=hiring_request.id)
        db.add(design)

    if body.screening_sections is not None:
        design.screening_sections = [section.model_dump() for section in body.screening_sections]
    if body.interview_sections is not None:
        design.interview_sections = [section.model_dump() for section in body.interview_sections]

    db.commit()
    db.refresh(design)

    sync_errors: list[str] = []
    if body.screening_sections is not None or body.interview_sections is not None:
        try:
            rh_job_id = await _resolve_rh_job(hiring_request, db)
            client = AiRecruitmentClient()
            result = await client.update_job_questions(
                rh_job_id,
                screening_questions=(
                    _flatten_sections(design.screening_sections)
                    if body.screening_sections is not None
                    else None
                ),
                interview_questions=(
                    _flatten_sections(design.interview_sections)
                    if body.interview_sections is not None
                    else None
                ),
                external_job_id=str(hiring_request.id),
            )
            if result is None:
                sync_errors.append(_POC_SYNC_ERROR)
            else:
                resolved_job_id = result.get("job_id")
                if resolved_job_id and str(resolved_job_id) != (hiring_request.rh_external_job_id or ""):
                    hiring_request.rh_external_job_id = str(resolved_job_id)
                    db.commit()
        except HTTPException:
            sync_errors.append(_POC_JOB_CREATE_ERROR)

    sync_status = "draft" if sync_errors else "synced"
    return _to_response(hiring_request.id, design, sync_status=sync_status, sync_errors=sync_errors)
