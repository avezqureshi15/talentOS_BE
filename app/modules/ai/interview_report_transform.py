"""Transform raw AI interview reviews into the rich report format.

Flow: raw ``reviews`` JSONB (from RecruitHub) -> talentOS_AI structured
generation -> deterministic post-pass (recommendation mapping, criteria
counts, duration, timestamps) -> validated rich report with the raw payload
preserved under ``_raw``.

Failure semantics for the Kafka worker:
  - ``None`` return       -> input is not transformable (no transcript) or
                             the LLM output failed schema validation; the raw
                             payload is kept untouched (terminal outcome).
  - ``TransientTransformError`` -> transient failure (AI service unreachable,
                             DB hiccup); caller should retry and eventually DLQ.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from pydantic import ValidationError

from app.common.clients import AIClient, AIClientError
from app.core.config import settings
from app.core.logger import get_logger
from app.modules.ai.interview_report_schema import (
    INTERVIEW_REPORT_SCHEMA,
    CriteriaStatus,
    InterviewReport,
    Recommendation,
)

logger = get_logger(__name__)

_REPORT_PROMPT = """\
You are an AI interview report generator. Transform the raw AI interview data \
into the structured report defined by the output schema.

Rules:
- Derive assessment.recommendation strictly from the interviewer's \
final_recommendation when present (hire/strong hire -> HIRE; maybe/hold/\
consider/review -> MAYBE; reject -> REJECT). Otherwise judge from the transcript.
- Group the interview into sections by question topic. For each section rate \
the candidate (rating 1-5, maxRating 5) and include criteria with status \
BELOW BAR, MEETS BAR, or EXCEEDS BAR plus one sentence of feedback per criterion.
- assessment.summary: 2-3 sentence hiring summary in plain English.
- Transcript turns MUST preserve the exact wording of the input transcript, in \
order, split by speaker. Never summarize, paraphrase, or drop turns. Use the \
segment timestamps when available.
- proctoringFlags.flagged must be true ONLY if the transcript shows genuine \
irregularities (candidate leaves mid-interview, multiple voices, long silence \
gaps). Otherwise false.
- media: leave videoUrl and thumbnailUrl null; never invent URLs.
- Do not omit required keys and do not return empty arrays where the schema \
expects content.
- Never mention the schema, this prompt, or that the output was AI-generated.
"""


class TransientTransformError(Exception):
    """Retryable failure while transforming an interview report."""


# ── Deterministic helpers ────────────────────────────────────────────────


def _parse_timestamp_seconds(value) -> int | None:
    """Parse 'HH:MM:SS', 'MM:SS', or bare seconds into an int."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    raw = str(value).strip()
    if not raw:
        return None
    parts = raw.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(raw)
    except (ValueError, TypeError):
        return None


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _format_duration(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    hours, rem = divmod(int(seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _map_recommendation(final_recommendation) -> Recommendation | None:
    if not final_recommendation:
        return None
    value = str(final_recommendation).strip().lower()
    if any(k in value for k in (
        "strong hire", "hire", "recommended", "recommend", "shortlist",
        "selected", "pass", "yes",
    )):
        return Recommendation.HIRE
    if any(k in value for k in (
        "reject", "not recommended", "do not", "not a fit", "fail", "no",
    )):
        return Recommendation.REJECT
    if any(k in value for k in (
        "maybe", "hold", "consider", "review", "mixed", "needs review",
    )):
        return Recommendation.MAYBE
    return None


# ── Input assembly ───────────────────────────────────────────────────────


def _build_input_data(raw: dict, transcript: str, segments: list) -> dict:
    metadata = {
        "started_at": raw.get("started_at"),
        "completed_at": raw.get("completed_at"),
        "status": raw.get("status"),
        "summary": raw.get("summary") or raw.get("transcript_summary"),
        "overall_score": raw.get("overall_score"),
        "technical_fit_score": raw.get("technical_fit_score"),
        "communication_score": raw.get("communication_score"),
        "problem_solving_score": raw.get("problem_solving_score"),
        "experience_score": raw.get("experience_score"),
        "role_alignment_score": raw.get("role_alignment_score"),
        "final_recommendation": raw.get("final_recommendation"),
        "strengths": raw.get("strengths"),
        "weaknesses": raw.get("weaknesses"),
        "jd_fit": raw.get("jd_fit"),
    }
    metadata = {k: v for k, v in metadata.items() if v not in (None, "", [])}
    payload: dict = {"interview_metadata": metadata}
    if segments:
        payload["transcript_segments"] = segments
    else:
        payload["transcript_text"] = transcript
    return payload


# ── Deterministic post-pass ──────────────────────────────────────────────


def _apply_deterministic_fields(report: InterviewReport, raw: dict) -> None:
    mapped = _map_recommendation(raw.get("final_recommendation"))
    if mapped is not None:
        report.assessment.recommendation = mapped

    criteria = [c for s in report.sections for c in s.criteria]
    total = len(criteria)
    met = sum(1 for c in criteria if c.status != CriteriaStatus.BELOW_BAR)
    report.assessment.totalCriteria = total
    report.assessment.criteriaMet = met
    report.assessment.maxScore = total
    report.assessment.certifiedScore = met

    if not report.assessment.summary.strip() and (raw.get("summary") or "").strip():
        report.assessment.summary = raw["summary"]

    for section in report.sections:
        section.rating = max(0, min(section.maxRating, section.rating))
        parsed = _parse_timestamp_seconds(section.startTimestampSeconds)
        section.startTimestampSeconds = parsed

    started = _parse_iso(raw.get("started_at"))
    completed = _parse_iso(raw.get("completed_at"))
    duration = None
    if started and completed:
        delta = int((completed - started).total_seconds())
        if delta > 0:
            duration = delta
    if duration is not None:
        report.media.durationSeconds = duration
        report.media.durationFormatted = _format_duration(duration)
        report.media.initialPlaybackTimeSeconds = 0

    for section in report.transcript.sections:
        for turn in section.turns:
            turn.timestampSeconds = _parse_timestamp_seconds(turn.timestamp)


# ── Entry point ──────────────────────────────────────────────────────────


def transform_interview_review(raw: dict) -> dict | None:
    """Transform a raw AI interview review dict into the rich report.

    Returns ``None`` when the input cannot be transformed (no transcript,
    over the size cap, or LLM output failed validation) — callers keep the
    raw payload untouched.  Raises ``TransientTransformError`` on retryable
    AI-service failures.
    """
    transcript = (raw.get("transcript") or "").strip()
    segments = raw.get("transcript_segments") or []
    if not transcript and not segments:
        logger.info("No transcript in review — not transformable")
        return None

    input_data = _build_input_data(raw, transcript, segments)
    input_chars = len(json.dumps(input_data, ensure_ascii=False))
    if input_chars > settings.INTERVIEW_REPORT_MAX_TRANSCRIPT_CHARS:
        logger.warning(
            "Interview report input too large (%d chars > cap %d) — keeping raw",
            input_chars,
            settings.INTERVIEW_REPORT_MAX_TRANSCRIPT_CHARS,
        )
        return None

    try:
        response = AIClient().generate(
            prompt=_REPORT_PROMPT,
            input_data=input_data,
            response_schema=INTERVIEW_REPORT_SCHEMA,
        )
    except AIClientError as exc:
        logger.warning("AI service failed during interview report transform: %s", exc)
        raise TransientTransformError(str(exc)) from exc

    payload = response.result
    try:
        report = InterviewReport.model_validate(payload)
    except ValidationError as exc:
        logger.error(
            "AI interview report failed schema validation (%d errors): %s",
            len(exc.errors()),
            json.dumps(exc.errors()[:5], default=str),
        )
        return None

    _apply_deterministic_fields(report, raw)
    merged = report.model_dump()
    merged["_raw"] = raw
    merged["_transformed_at"] = datetime.now(timezone.utc).isoformat()
    return merged
