import copy
import uuid
from typing import Any, Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.common.clients.ai_client import AIClient, AIClientError
from app.core.ai_recruitment_client import AiRecruitmentClient
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.hiring_requests.location_utils import format_locations
from app.modules.interview_designs.interview_design_model import InterviewDesign
from app.modules.interview_designs.interview_design_schema import (
    InterviewDesignGenerate,
    InterviewDesignResponse,
    InterviewDesignUpdate,
)

_DEFAULT_SECTION_ID = "section-1"
_DEFAULT_SECTION_TITLE = "Q&A"
_DEFAULT_SECTION_TYPE = "Q&A"
_DEFAULT_SECTION_DEPTH = "Standard"
_DEFAULT_INTERVIEW_MINUTES = 5
_DEFAULT_SCREENING_MINUTES = 0.25
_DEFAULT_QUESTION_SCORE = 5
_POC_SYNC_ERROR = "ai-recruitment-poc unreachable — design saved as draft"
_POC_JOB_CREATE_ERROR = "Failed to create linked job in ai-recruitment-poc"
_DEFAULT_SCREENING_SECTIONS: list[dict] = [
    {
        "id": "screening-section-availability",
        "title": "Availability & Notice Period",
        "type": "Q&A",
        "depth": "Standard",
        "description": "Checks when the candidate can join and their notice constraints.",
        "questions": [
            {
                "id": "screening-default-availability",
                "question": "When are you available to start a new role? Are you currently looking actively?",
                "score": _DEFAULT_QUESTION_SCORE,
                "timeAllocationMinutes": _DEFAULT_SCREENING_MINUTES,
                "expected_points": [],
            },
            {
                "id": "screening-default-notice",
                "question": "What is your notice period at your current company?",
                "score": _DEFAULT_QUESTION_SCORE,
                "timeAllocationMinutes": _DEFAULT_SCREENING_MINUTES,
                "expected_points": [],
            },
        ],
    },
    {
        "id": "screening-section-employment",
        "title": "Current Employment & Experience",
        "type": "Q&A",
        "depth": "Standard",
        "description": "Confirms current role and relevance of prior experience to the position.",
        "questions": [
            {
                "id": "screening-default-employment",
                "question": "Are you currently employed? What is your current role and company?",
                "score": _DEFAULT_QUESTION_SCORE,
                "timeAllocationMinutes": _DEFAULT_SCREENING_MINUTES,
                "expected_points": [],
            },
            {
                "id": "screening-default-experience",
                "question": "Can you briefly describe your most relevant experience for this role?",
                "score": _DEFAULT_QUESTION_SCORE,
                "timeAllocationMinutes": _DEFAULT_SCREENING_MINUTES,
                "expected_points": [],
            },
        ],
    },
    {
        "id": "screening-section-compensation",
        "title": "Compensation & Expectations",
        "type": "Q&A",
        "depth": "Standard",
        "description": "Aligns current compensation with the candidate's salary expectations.",
        "questions": [
            {
                "id": "screening-default-current-ctc",
                "question": "What is your current compensation package (annual CTC)?",
                "score": _DEFAULT_QUESTION_SCORE,
                "timeAllocationMinutes": _DEFAULT_SCREENING_MINUTES,
                "expected_points": [],
            },
            {
                "id": "screening-default-expected-ctc",
                "question": "What are your salary expectations for this role?",
                "score": _DEFAULT_QUESTION_SCORE,
                "timeAllocationMinutes": _DEFAULT_SCREENING_MINUTES,
                "expected_points": [],
            },
        ],
    },
    {
        "id": "screening-section-preferences",
        "title": "Work Preferences & Interest",
        "type": "Q&A",
        "depth": "Standard",
        "description": "Confirms work-mode preference and interest in moving forward.",
        "questions": [
            {
                "id": "screening-default-location",
                "question": "What is your remote, hybrid, or on-site preference?",
                "score": _DEFAULT_QUESTION_SCORE,
                "timeAllocationMinutes": _DEFAULT_SCREENING_MINUTES,
                "expected_points": [],
            },
            {
                "id": "screening-default-interest",
                "question": "Are you interested in moving forward with this opportunity?",
                "score": _DEFAULT_QUESTION_SCORE,
                "timeAllocationMinutes": _DEFAULT_SCREENING_MINUTES,
                "expected_points": [],
            },
        ],
    },
]


def _build_default_screening_sections() -> list[dict]:
    """Section-wise screening seed for a fresh interview design.

    The 8 canonical screening questions are distributed across 4 titled
    sections (matching the generate/update flows); the flat form is derived
    at sync time via ``_flatten_sections`` when pushing to ai-recruitment-poc.
    """
    return copy.deepcopy(_DEFAULT_SCREENING_SECTIONS)


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
                    "expected_points": q.get("expected_points") or [],
                }
                for q in questions
            ],
        }
    ]


def _flatten_sections(sections: list[dict]) -> list[dict]:
    flat: list[dict] = []
    for section in sections:
        for q in section.get("questions", []):
            item = {"id": q["id"], "question": q["question"], "score": q["score"]}
            expected_points = q.get("expected_points")
            if expected_points:
                item["expected_points"] = expected_points
            flat.append(item)
    return flat


_GENERATE_DEFAULT_COUNT = 8

_INTERVIEW_GENERATE_PROMPT = """\
You are a senior technical interviewer designing questions for a job listing.

Generate {count} high-quality, ORAL-ANSWERABLE technical interview questions for the role.

Requirements:
- Each question must be answerable verbally by a candidate (no code writing, no trivia).
- Spread across fundamentals, hands-on experience, and design/judgment relevant to the role.
- Score each question 1-10 based on how important it is for this role.
- expected_points: 2-4 short phrases describing what a strong answer should cover.
- timeAllocationMinutes: estimate how long a candidate should be given to answer each
  question, 1-60. Use roughly 2-3 for quick recall/fact questions, 5 for standard
  experience-based questions, and 8-10 for complex scenario, system design, or deep-dive
  questions.
- Never mention the job description, the interview format, or that questions were generated.
"""

_SCREENING_GENERATE_PROMPT = """\
You are a recruitment specialist designing a pre-screening phone call for a job listing.

Generate {count} screening questions that an HR partner would ask a candidate on a short phone call.

Requirements:
- Cover availability/notice period, current and expected compensation, location preference,
  and relevant experience alignment with the role. Include any role-specific screening concern.
- Each question must be short, spoken naturally, and answerable in one or two sentences.
- Never mention the job description, the interview format, or that questions were generated.
"""

_INTERVIEW_QUESTIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "score": {"type": "integer"},
                    "expected_points": {"type": "array", "items": {"type": "string"}},
                    "timeAllocationMinutes": {"type": "integer"},
                },
                "required": ["question", "score", "expected_points", "timeAllocationMinutes"],
            },
        }
    },
    "required": ["questions"],
}

_SCREENING_QUESTIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        }
    },
    "required": ["questions"],
}

_ALLOWED_SECTION_TYPES: set[str] = {"INTRO", "Q&A", "SYSTEM DESIGN", "SCENARIO", "CLOSING", "CUSTOM"}
_ALLOWED_SECTION_DEPTHS: set[str] = {"Standard", "Deep Dive"}

_REVIEW_SECTIONS_GENERATE_PROMPT = """\
You are a senior interviewer designing post-interview candidate evaluation questions for a job listing.

Generate {count} evaluation questions grouped into sections.

Requirements:
- Create 3-5 sections, each covering a distinct evaluation dimension relevant to this role
  (for example: Technical Competence, Problem-Solving & Decision Making, Communication,
  Collaboration & Ownership, Culture Fit).
- Distribute the {count} questions across the sections so every section has at least one question.
- Each question must:
  - be rateable on a rubric (not a yes/no question);
  - have a score from 1 to 10 indicating how important it is for evaluating this specific role;
  - include expected_points: 2-4 short phrases describing what a strong candidate should exhibit.
- section.type must be one of: INTRO, Q&A, SYSTEM DESIGN, SCENARIO, CLOSING, CUSTOM.
- section.depth must be one of: Standard, Deep Dive.
- section.description is a short note describing what this section evaluates.
- Never mention the job description, the interview format, or that questions were generated.
"""

_REVIEW_SECTIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["INTRO", "Q&A", "SYSTEM DESIGN", "SCENARIO", "CLOSING", "CUSTOM"],
                    },
                    "depth": {"type": "string", "enum": ["Standard", "Deep Dive"]},
                    "description": {"type": "string"},
                    "questions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"},
                                "score": {"type": "integer"},
                                "expected_points": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["question", "score", "expected_points"],
                        },
                    },
                },
                "required": ["title", "type", "questions"],
            },
        }
    },
    "required": ["sections"],
}


def _job_input_data(hiring_request: HiringRequest) -> dict[str, Any]:
    return {
        "job_title": hiring_request.title,
        "job_description": hiring_request.description,
        "requirements": hiring_request.requirements,
        "location": format_locations(hiring_request.location),
        "department": hiring_request.department,
        "employment_type": hiring_request.type,
    }


def _clean_generated_questions(
    raw_questions: list[dict],
    kind: Literal["screening", "interview", "review"],
) -> list[dict]:
    cleaned: list[dict] = []
    for q in raw_questions:
        question = str(q.get("question") or "").strip()
        if not question:
            continue
        item: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "question": question,
        }
        if kind in ("interview", "review"):
            try:
                score = int(q.get("score"))
            except (TypeError, ValueError):
                score = _DEFAULT_QUESTION_SCORE
            item["score"] = max(1, min(10, score))
            expected_points = q.get("expected_points")
            if isinstance(expected_points, list):
                points = [str(p).strip() for p in expected_points if str(p).strip()]
                if points:
                    item["expected_points"] = points
            if kind == "interview":
                try:
                    minutes = int(q.get("timeAllocationMinutes"))
                except (TypeError, ValueError):
                    minutes = _DEFAULT_INTERVIEW_MINUTES
                item["timeAllocationMinutes"] = max(1, min(60, minutes))
            else:
                item["timeAllocationMinutes"] = 0
        else:
            item["score"] = _DEFAULT_QUESTION_SCORE
        cleaned.append(item)
    return cleaned


def _clean_generated_sections(raw_sections: list[dict]) -> list[dict]:
    cleaned_sections: list[dict] = []
    for sec in raw_sections:
        if not isinstance(sec, dict):
            continue
        title = str(sec.get("title") or "").strip()
        raw_questions = sec.get("questions")
        if not title or not isinstance(raw_questions, list):
            continue
        questions = _clean_generated_questions(raw_questions, "review")
        if not questions:
            continue
        section_type = str(sec.get("type") or "").strip().upper()
        if section_type not in _ALLOWED_SECTION_TYPES:
            section_type = _DEFAULT_SECTION_TYPE
        depth = str(sec.get("depth") or "").strip()
        if depth not in _ALLOWED_SECTION_DEPTHS:
            depth = _DEFAULT_SECTION_DEPTH
        cleaned_sections.append(
            {
                "id": str(uuid.uuid4()),
                "title": title,
                "type": section_type,
                "depth": depth,
                "description": str(sec.get("description") or "").strip(),
                "questions": questions,
            }
        )
    return cleaned_sections


async def generate_design(
    hiring_request_id: str,
    body: InterviewDesignGenerate,
    db: Session,
) -> InterviewDesignResponse:
    hiring_request = db.query(HiringRequest).filter(HiringRequest.id == hiring_request_id).first()
    if not hiring_request:
        raise HTTPException(status_code=404, detail="Hiring request not found")

    is_interview = body.kind == "interview"
    is_review = body.kind == "review"
    if is_interview:
        prompt = _INTERVIEW_GENERATE_PROMPT.format(count=body.count)
        response_schema = _INTERVIEW_QUESTIONS_SCHEMA
    elif is_review:
        prompt = _REVIEW_SECTIONS_GENERATE_PROMPT.format(count=body.count)
        response_schema = _REVIEW_SECTIONS_SCHEMA
    else:
        prompt = _SCREENING_GENERATE_PROMPT.format(count=body.count)
        response_schema = _SCREENING_QUESTIONS_SCHEMA

    try:
        result = AIClient().generate(
            prompt=prompt,
            input_data=_job_input_data(hiring_request),
            response_schema=response_schema,
        )
    except AIClientError as exc:
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail=exc.message,
        ) from exc

    if is_review:
        raw_sections = result.result.get("sections") if isinstance(result.result, dict) else None
        if not isinstance(raw_sections, list) or not raw_sections:
            raise HTTPException(
                status_code=502,
                detail="AI generation returned no sections — retry or adjust the request.",
            )
        generated_sections = _clean_generated_sections(raw_sections)
        if not generated_sections:
            raise HTTPException(
                status_code=502,
                detail="AI generation returned empty sections — retry or adjust the request.",
            )
        generated: list[dict] | None = None
    else:
        raw_questions = result.result.get("questions") if isinstance(result.result, dict) else None
        if not isinstance(raw_questions, list) or not raw_questions:
            raise HTTPException(
                status_code=502,
                detail="AI generation returned no questions — retry or adjust the request.",
            )
        generated = _clean_generated_questions(raw_questions, body.kind)
        if not generated:
            raise HTTPException(
                status_code=502,
                detail="AI generation returned empty questions — retry or adjust the request.",
            )

    design = (
        db.query(InterviewDesign)
        .filter(InterviewDesign.hiring_request_id == hiring_request.id)
        .first()
    )
    if design is None:
        design = InterviewDesign(hiring_request_id=hiring_request.id)
        db.add(design)

    if is_review:
        design.review_sections = generated_sections
    else:
        default_minutes = _DEFAULT_INTERVIEW_MINUTES if is_interview else _DEFAULT_SCREENING_MINUTES
        section = _build_seed_section(generated, default_minutes)
        if is_interview:
            design.interview_sections = section
        else:
            design.screening_sections = section
    db.commit()
    db.refresh(design)

    # Review questions are not synced to ai-recruitment-poc
    sync_errors: list[str] = []
    if not is_review:
        try:
            rh_job_id = await _resolve_rh_job(hiring_request, db)
            client = AiRecruitmentClient(tenant_id=hiring_request.tenant_id)
            result = await client.update_job_questions(
                rh_job_id,
                screening_questions=(
                    _flatten_sections(design.screening_sections) if not is_interview else None
                ),
                interview_questions=(
                    _flatten_sections(design.interview_sections) if is_interview else None
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
        review_sections=design.review_sections or [],
        updated_at=design.updated_at,
        sync_status=sync_status,
        sync_errors=sync_errors or [],
    )


async def _resolve_rh_job(hiring_request: HiringRequest, db: Session) -> str:
    from app.modules.hiring_requests.rh_job_resolver import resolve_or_create_rh_job

    rh_job_id = await resolve_or_create_rh_job(db, hiring_request)
    if not rh_job_id:
        raise HTTPException(status_code=502, detail=_POC_JOB_CREATE_ERROR)
    return rh_job_id


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

    screening_sections = _build_default_screening_sections()
    interview_sections: list[dict] = []
    if hiring_request.rh_external_job_id:
        client = AiRecruitmentClient(tenant_id=hiring_request.tenant_id)
        result = await client.get_job_questions(
            hiring_request.rh_external_job_id,
            external_job_id=str(hiring_request.id),
        )
        if result:
            # Screening stays section-wise from the canonical defaults; the
            # POC copy is flat by design and only interview questions are
            # restored here for an already-linked job.
            interview_sections = _build_seed_section(
                result.get("interview_questions") or [],
                _DEFAULT_INTERVIEW_MINUTES,
            )

    review_sections: list[dict] = []
    try:
        review_result = AIClient().generate(
            prompt=_REVIEW_SECTIONS_GENERATE_PROMPT.format(count=_GENERATE_DEFAULT_COUNT),
            input_data=_job_input_data(hiring_request),
            response_schema=_REVIEW_SECTIONS_SCHEMA,
        )
        raw = review_result.result.get("sections") if isinstance(review_result.result, dict) else None
        if isinstance(raw, list) and raw:
            review_sections = _clean_generated_sections(raw)
    except Exception:
        pass  # leave review_sections as [] on any AI failure

    design = InterviewDesign(
        hiring_request_id=hiring_request.id,
        screening_sections=screening_sections,
        interview_sections=interview_sections,
        review_sections=review_sections,
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
    if body.review_sections is not None:
        design.review_sections = [section.model_dump() for section in body.review_sections]

    db.commit()
    db.refresh(design)

    sync_errors: list[str] = []
    if body.screening_sections is not None or body.interview_sections is not None:
        try:
            rh_job_id = await _resolve_rh_job(hiring_request, db)
            client = AiRecruitmentClient(tenant_id=hiring_request.tenant_id)
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
