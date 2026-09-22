from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    title: str
    period_start: date
    period_end: date
    summary: str
    status: str
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReportCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    period_start: date
    period_end: date
    summary: str = Field(min_length=2)
    status: str = Field(default="draft", pattern="^(draft|published)$")

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("O fim do período não pode ser anterior ao início")
        return self


class ReportUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    period_start: date | None = None
    period_end: date | None = None
    summary: str | None = Field(default=None, min_length=2)
    status: str | None = Field(default=None, pattern="^(draft|published)$")
