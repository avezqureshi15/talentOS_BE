"""Structured AI interview report format.

This is the target shape for the rich interview report stored in the
``reviews`` JSONB (entity_type ``ai_interview``) after the async transform
worker runs.  The raw payload from RecruitHub is preserved under ``_raw``.

The JSON Schema in ``INTERVIEW_REPORT_SCHEMA`` is what we send to
talentOS_AI's ``/api/v1/generate`` endpoint (hand-written, no ``$defs``,
matching the pattern in ``interview_design_service``).  The Pydantic models
below are used to validate the LLM output and for the deterministic
post-pass.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Recommendation(str, Enum):
    HIRE = "HIRE"
    MAYBE = "MAYBE"
    REJECT = "REJECT"


class CriteriaStatus(str, Enum):
    BELOW_BAR = "BELOW BAR"
    MEETS_BAR = "MEETS BAR"
    EXCEEDS_BAR = "EXCEEDS BAR"


class SpeakerRole(str, Enum):
    CANDIDATE = "CANDIDATE"
    INTERVIEWER = "INTERVIEWER"


class Assessment(BaseModel):
    recommendation: Recommendation
    certifiedScore: int
    maxScore: int
    criteriaMet: int
    totalCriteria: int
    summary: str


class MediaInfo(BaseModel):
    videoUrl: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    durationSeconds: Optional[int] = None
    durationFormatted: Optional[str] = None
    initialPlaybackTimeSeconds: int = 0


class SectionCriterion(BaseModel):
    id: str
    title: str
    status: CriteriaStatus
    feedback: str = ""


class InterviewSection(BaseModel):
    id: str
    title: str
    rating: int = Field(default=0, ge=0)
    maxRating: int = Field(default=5, gt=0)
    startTimestampSeconds: Optional[int] = None
    problemStatement: str = ""
    keyTakeaways: list[str] = Field(default_factory=list)
    criteria: list[SectionCriterion] = Field(default_factory=list)


class ProctoringFlags(BaseModel):
    flagged: bool = False
    summary: Optional[str] = None


class TranscriptTurn(BaseModel):
    speakerRole: SpeakerRole
    speakerName: Optional[str] = None
    timestamp: Optional[str] = None
    timestampSeconds: Optional[int] = None
    text: str


class TranscriptSection(BaseModel):
    id: str
    title: str
    turns: list[TranscriptTurn] = Field(default_factory=list)


class Transcript(BaseModel):
    sections: list[TranscriptSection] = Field(default_factory=list)


class InterviewReport(BaseModel):
    assessment: Assessment
    media: MediaInfo
    sections: list[InterviewSection] = Field(default_factory=list)
    proctoringFlags: ProctoringFlags = Field(default_factory=ProctoringFlags)
    transcript: Transcript = Field(default_factory=Transcript)


INTERVIEW_REPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "assessment": {
            "type": "object",
            "properties": {
                "recommendation": {"type": "string", "enum": ["HIRE", "MAYBE", "REJECT"]},
                "certifiedScore": {"type": "integer"},
                "maxScore": {"type": "integer"},
                "criteriaMet": {"type": "integer"},
                "totalCriteria": {"type": "integer"},
                "summary": {"type": "string"},
            },
            "required": [
                "recommendation", "certifiedScore", "maxScore",
                "criteriaMet", "totalCriteria", "summary",
            ],
        },
        "media": {
            "type": "object",
            "properties": {
                "videoUrl": {"type": ["string", "null"]},
                "thumbnailUrl": {"type": ["string", "null"]},
                "durationSeconds": {"type": ["integer", "null"]},
                "durationFormatted": {"type": ["string", "null"]},
                "initialPlaybackTimeSeconds": {"type": "integer"},
            },
            "required": [
                "videoUrl", "thumbnailUrl", "durationSeconds",
                "durationFormatted", "initialPlaybackTimeSeconds",
            ],
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "rating": {"type": "integer"},
                    "maxRating": {"type": "integer"},
                    "startTimestampSeconds": {"type": ["integer", "null"]},
                    "problemStatement": {"type": "string"},
                    "keyTakeaways": {"type": "array", "items": {"type": "string"}},
                    "criteria": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "status": {"type": "string", "enum": ["BELOW BAR", "MEETS BAR", "EXCEEDS BAR"]},
                                "feedback": {"type": "string"},
                            },
                            "required": ["id", "title", "status", "feedback"],
                        },
                    },
                },
                "required": [
                    "id", "title", "rating", "maxRating",
                    "startTimestampSeconds", "problemStatement",
                    "keyTakeaways", "criteria",
                ],
            },
        },
        "proctoringFlags": {
            "type": "object",
            "properties": {
                "flagged": {"type": "boolean"},
                "summary": {"type": ["string", "null"]},
            },
            "required": ["flagged", "summary"],
        },
        "transcript": {
            "type": "object",
            "properties": {
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "turns": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "speakerRole": {"type": "string", "enum": ["CANDIDATE", "INTERVIEWER"]},
                                        "speakerName": {"type": ["string", "null"]},
                                        "timestamp": {"type": ["string", "null"]},
                                        "timestampSeconds": {"type": ["integer", "null"]},
                                        "text": {"type": "string"},
                                    },
                                    "required": [
                                        "speakerRole", "speakerName",
                                        "timestamp", "timestampSeconds", "text",
                                    ],
                                },
                            },
                        },
                        "required": ["id", "title", "turns"],
                    },
                }
            },
            "required": ["sections"],
        },
    },
    "required": ["assessment", "media", "sections", "proctoringFlags", "transcript"],
}


class InterviewReportMessage(BaseModel):
    """Kafka message enqueued after a raw AI interview result is persisted.

    The worker re-reads the review row from the DB by ``round_id``, so the
    message stays tiny even for 100k+ char transcripts.
    """

    round_id: uuid.UUID
    entity_type: str = "ai_interview"
