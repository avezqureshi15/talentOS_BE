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
    timeAllocationMinutes: int = Field(ge=0, le=60)
    expected_points: list[str] = Field(default_factory=list)


class ScreeningDesignQuestion(InterviewDesignQuestion):
    timeAllocationMinutes: float = Field(ge=0.25, le=2)


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
    review_sections: list[InterviewDesignSection] | None = None


class InterviewDesignGenerate(BaseModel):
    kind: Literal["screening", "interview", "review"]
    count: int = Field(default=8, ge=1, le=15)


class InterviewDesignResponse(BaseModel):
    hiring_request_id: uuid.UUID
    screening_sections: list[dict]
    interview_sections: list[dict]
    review_sections: list[dict]
    # Whether each kind has real AI-generated (or, for interview, already
    # poc-linked) content — the FE auto-fills a kind exactly once when its
    # flag is false, and never re-fires once true.
    screening_ai_generated: bool
    interview_ai_generated: bool
    review_ai_generated: bool
    updated_at: datetime
    sync_status: Literal["synced", "draft"]
    sync_errors: list[str] = Field(default_factory=list)
