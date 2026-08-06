"""Pydantic schema mirroring FE CandidateEvaluationData. Kept 1:1 with
`talentOS_FE/src/app/dashboard/round-details/pages/round-details.types.ts`.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class EvidencePoint(BaseModel):
    type: Literal["positive", "negative", "warning"]
    text: str


class SubCriteria(BaseModel):
    title: str
    status: Literal["BELOW_BAR", "MEETS_BAR", "ABOVE_BAR"]
    points: list[EvidencePoint]


class EvaluationTopic(BaseModel):
    id: str
    title: str
    rating: float
    maxRating: float
    summaryBullets: list[str]
    subCriteria: list[SubCriteria]
    timestampStart: int
    problemStatement: Optional[str] = None


class TranscriptUtterance(BaseModel):
    id: str
    speaker: Literal["INTERVIEWER", "CANDIDATE"]
    timestamp: str
    timeInSeconds: int
    text: str


class TranscriptSection(BaseModel):
    id: str
    title: str
    utterances: list[TranscriptUtterance]


class AiInterviewTemplateResponse(BaseModel):
    candidateName: str
    email: str
    status: str
    jobTitle: str
    appliedDate: str
    aiRecommendation: Literal["REJECT", "ADVANCE", "POTENTIAL_FIT"]
    aiSummary: str
    overallScore: float
    criteriaMet: int
    totalCriteria: int
    topics: list[EvaluationTopic]
    transcript: list[TranscriptUtterance]
    transcriptSections: list[TranscriptSection]
    interviewUrl: Optional[str] = None
    recordingUrl: Optional[str] = None
