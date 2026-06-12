from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=10000)


class TodoUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=10000)
    is_completed: bool | None = Field(None)


class TodoResponse(BaseModel):
    id: int
    title: str
    description: str | None
    is_completed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
