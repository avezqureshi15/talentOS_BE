"""Pure functions that reshape POC's flat interview detail into the FE
template's `CandidateEvaluationData` payload.

No I/O. No exceptions escape — missing fields yield sane defaults so the
FE always renders without crashing.
"""

from __future__ import annotations

from typing import Any

from app.modules.hiring_requests.ai_interview_template_constants import (
    BELOW_BAR_LT,
    CANDIDATE_PREFIXES,
    CRITERIA_MET_GTE,
    DEFAULT_SUBCRITERIA_TITLE,
    DEFAULT_TRANSCRIPT_SECTION_TITLE,
    DEFAULT_VERDICT,
    DIMENSIONS,
    INTERVIEWER_PREFIXES,
    MAX_RATING,
    MEETS_BAR_LT,
    TOTAL_CRITERIA,
    VERDICT_MAP,
)


def build_interview_template_response(
    detail: dict[str, Any],
    *,
    candidate_name: str | None,
    candidate_email: str | None,
    role_title: str | None,
    applied_date: str | None,
    recording_url: str | None = None,
) -> dict[str, Any]:
    scores = _dimension_scores(detail)
    return {
        "candidateName": (candidate_name or "").strip() or "Candidate",
        "email": (candidate_email or "").strip(),
        "status": (detail.get("status") or "").strip(),
        "jobTitle": (role_title or "").strip(),
        "appliedDate": applied_date or "",
        "aiRecommendation": _verdict(detail.get("final_recommendation")),
        "aiSummary": _summary(detail),
        "overallScore": _score(detail.get("overall_score")),
        "criteriaMet": sum(1 for s in scores.values() if s is not None and s >= CRITERIA_MET_GTE),
        "totalCriteria": TOTAL_CRITERIA,
        "topics": _topics(detail, scores),
        "transcript": _flat_transcript(_transcript_sections(detail)),
        "transcriptSections": _transcript_sections(detail),
        "interviewUrl": detail.get("interview_url"),
        "recordingUrl": recording_url,
    }


# ---------------------------------------------------------------------------
# verdict / summary / score primitives
# ---------------------------------------------------------------------------

def _verdict(final_recommendation: Any) -> str:
    key = str(final_recommendation or "").strip().lower()
    return VERDICT_MAP.get(key, DEFAULT_VERDICT)


def _summary(detail: dict[str, Any]) -> str:
    return (detail.get("summary") or detail.get("transcript_summary") or "").strip()


def _score(raw: Any) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    # POC assessment prompt uses 0..5 already; if a call ever emits 0..10 we
    # divide by 2 here so the template's /5.0 badge stays truthful.
    if value > MAX_RATING:
        value = value / 2.0
    return round(value, 1)


def _dimension_scores(detail: dict[str, Any]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for dim in DIMENSIONS:
        raw = detail.get(dim["key"])
        out[dim["id"]] = None if raw is None else _score(raw)
    return out


def _status_from_score(score: float | None) -> str:
    if score is None:
        return "BELOW_BAR"
    if score < BELOW_BAR_LT:
        return "BELOW_BAR"
    if score < MEETS_BAR_LT:
        return "MEETS_BAR"
    return "ABOVE_BAR"


# ---------------------------------------------------------------------------
# topics — one per dimension, evidence distributed by keyword match
# ---------------------------------------------------------------------------

def _topics(detail: dict[str, Any], scores: dict[str, float | None]) -> list[dict[str, Any]]:
    strengths = _coerce_str_list(detail.get("strengths"))
    weaknesses = _coerce_str_list(detail.get("weaknesses"))
    strengths_by_dim = _distribute_by_keywords(strengths)
    weaknesses_by_dim = _distribute_by_keywords(weaknesses)

    topics: list[dict[str, Any]] = []
    for dim in DIMENSIONS:
        score = scores.get(dim["id"])
        s_bullets = strengths_by_dim.get(dim["id"], [])
        w_bullets = weaknesses_by_dim.get(dim["id"], [])
        summary_bullets = [*s_bullets, *w_bullets]
        points = [
            *({"type": "positive", "text": text} for text in s_bullets),
            *({"type": "negative", "text": text} for text in w_bullets),
        ]
        topics.append({
            "id": dim["id"],
            "title": dim["title"],
            "rating": score if score is not None else 0.0,
            "maxRating": MAX_RATING,
            "summaryBullets": summary_bullets,
            "subCriteria": [{
                "title": DEFAULT_SUBCRITERIA_TITLE,
                "status": _status_from_score(score),
                "points": points,
            }],
            "timestampStart": 0,
        })
    return topics


def _coerce_str_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _distribute_by_keywords(items: list[str]) -> dict[str, list[str]]:
    """Slot each item under the dimension whose keywords best match; round-robin the leftovers."""
    buckets: dict[str, list[str]] = {dim["id"]: [] for dim in DIMENSIONS}
    unmatched: list[str] = []
    for item in items:
        needle = item.lower()
        placed = False
        for dim in DIMENSIONS:
            if any(kw in needle for kw in dim["keywords"]):
                buckets[dim["id"]].append(item)
                placed = True
                break
        if not placed:
            unmatched.append(item)
    # Round-robin unmatched across dimensions so no single topic looks empty
    # solely because keywords didn't match.
    for idx, item in enumerate(unmatched):
        buckets[DIMENSIONS[idx % len(DIMENSIONS)]["id"]].append(item)
    return buckets


# ---------------------------------------------------------------------------
# transcript — structured segments preferred, raw text parsed as fallback
# ---------------------------------------------------------------------------

def _transcript_sections(detail: dict[str, Any]) -> list[dict[str, Any]]:
    utterances = _utterances_from_segments(detail.get("transcript_segments"))
    if not utterances:
        utterances = _utterances_from_raw(detail.get("transcript"))
    if not utterances:
        return []
    return [{
        "id": "section-1",
        "title": DEFAULT_TRANSCRIPT_SECTION_TITLE,
        "utterances": utterances,
    }]


def _utterances_from_segments(segments: Any) -> list[dict[str, Any]]:
    if not isinstance(segments, list) or not segments:
        return []
    out: list[dict[str, Any]] = []
    for idx, seg in enumerate(segments):
        if not isinstance(seg, dict):
            continue
        text = str(seg.get("text") or seg.get("content") or "").strip()
        if not text:
            continue
        raw_speaker = str(seg.get("speaker") or seg.get("role") or "").strip().lower()
        speaker = "INTERVIEWER" if raw_speaker in ("interviewer", "assistant", "ai", "bot") else "CANDIDATE"
        ts_raw = seg.get("timestamp") if "timestamp" in seg else seg.get("time")
        secs, ts_display = _normalize_timestamp(ts_raw)
        out.append({
            "id": f"utt-{idx}",
            "speaker": speaker,
            "timestamp": ts_display,
            "timeInSeconds": secs,
            "text": text,
        })
    return out


def _utterances_from_raw(raw: Any) -> list[dict[str, Any]]:
    text = str(raw or "").strip()
    if not text:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    out: list[dict[str, Any]] = []
    for idx, line in enumerate(lines):
        lower = line.lower()
        speaker = "CANDIDATE"
        body = line
        for prefix in INTERVIEWER_PREFIXES:
            if lower.startswith(prefix):
                speaker = "INTERVIEWER"
                body = line[len(prefix):].strip()
                break
        else:
            for prefix in CANDIDATE_PREFIXES:
                if lower.startswith(prefix):
                    speaker = "CANDIDATE"
                    body = line[len(prefix):].strip()
                    break
        if not body:
            continue
        out.append({
            "id": f"utt-{idx}",
            "speaker": speaker,
            "timestamp": "",
            "timeInSeconds": 0,
            "text": body,
        })
    return out


def _flat_transcript(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [u for section in sections for u in section.get("utterances", [])]


def _normalize_timestamp(raw: Any) -> tuple[int, str]:
    """Accept int seconds, float seconds, or 'MM:SS'/'HH:MM:SS' strings."""
    if isinstance(raw, (int, float)):
        secs = int(raw)
        return secs, _format_seconds(secs)
    text = str(raw or "").strip()
    if not text:
        return 0, ""
    if ":" in text:
        parts = text.split(":")
        try:
            nums = [int(p) for p in parts]
        except ValueError:
            return 0, text
        secs = 0
        for n in nums:
            secs = secs * 60 + n
        return secs, text
    try:
        secs = int(float(text))
        return secs, _format_seconds(secs)
    except ValueError:
        return 0, text


def _format_seconds(secs: int) -> str:
    if secs < 0:
        secs = 0
    m, s = divmod(secs, 60)
    if m < 60:
        return f"{m:02d}:{s:02d}"
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
