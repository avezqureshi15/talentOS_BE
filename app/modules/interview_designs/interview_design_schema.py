import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

InterviewSectionType = Literal["INTRO", "Q&A", "SYSTEM DESIGN", "SCENARIO", "CLOSING", "CUSTOM"]
InterviewSectionDepth = Literal["Standard", "Deep Dive"]


class InterviewDesignQuestion(BaseModel):
    id: str
    question: str
    score: int = Field(ge=1, le=10)
    timeAllocationMinutes: int = Field(ge=1, le=60)
    expected_points: list[str] = Field(default_factory=list)


class ScreeningDesignQuestion(InterviewDesignQuestion):
    timeAllocationMinutes: int = Field(ge=1, le=2)


class InterviewDesignSection(BaseModel):
    id: str
    title: str
    type: InterviewSectionType
    description: str = ""
    depth: InterviewSectionDepth = "Standard"
    questions: list[InterviewDesignQuestion] = Field(default_factory=list)


class ScreeningDesignSection(BaseModel):
    id: str
    title: str
    type: InterviewSectionType
    description: str = ""
    depth: InterviewSectionDepth = "Standard"
    questions: list[ScreeningDesignQuestion] = Field(default_factory=list)


class InterviewDesignUpdate(BaseModel):
    screening_sections: list[ScreeningDesignSection] | None = None
    interview_sections: list[InterviewDesignSection] | None = None


class InterviewDesignGenerate(BaseModel):
    kind: Literal["screening", "interview"]
    count: int = Field(default=8, ge=1, le=15)


class InterviewDesignResponse(BaseModel):
    hiring_request_id: uuid.UUID
    screening_sections: list[dict]
    interview_sections: list[dict]
    updated_at: datetime
    sync_status: Literal["synced", "draft"]
    sync_errors: list[str] = Field(default_factory=list)
