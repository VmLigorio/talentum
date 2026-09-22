from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ActionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    goal_id: int | None
    title: str
    description: str | None
    due_date: date | None
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime


class ActionItemCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    goal_id: int | None = Field(default=None, gt=0)
    due_date: date | None = None
    status: str = Field(default="planned", pattern="^(planned|in_progress|completed)$")
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")


class ActionItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    goal_id: int | None = Field(default=None, gt=0)
    due_date: date | None = None
    status: str | None = Field(default=None, pattern="^(planned|in_progress|completed)$")
    priority: str | None = Field(default=None, pattern="^(low|medium|high)$")
