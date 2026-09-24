# Talentum — backend/app/schemas/suitability.py
# Responsabilidade: Define os contratos públicos do questionário, da avaliação e da carteira modelo.
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SuitabilityOption(BaseModel):
    value: str
    label: str


class SuitabilityQuestion(BaseModel):
    key: str
    label: str
    description: str
    options: list[SuitabilityOption]


class SuitabilityQuestionnaireResponse(BaseModel):
    objectives: list[dict[str, str]]
    questions: list[SuitabilityQuestion]
    disclaimer: str


class SuitabilityAssessmentCreate(BaseModel):
    objective: Literal["longevity", "dividends", "long_term", "short_term"]
    answers: dict[str, str] = Field(min_length=6, max_length=6)


class SuitabilityAllocation(BaseModel):
    asset_class: str
    label: str
    percentage: int = Field(ge=0, le=100)
    rationale: str


class SuitabilityRecommendation(BaseModel):
    title: str
    summary: str
    allocations: list[SuitabilityAllocation]
    guardrails: list[str]


class SuitabilityAssessmentResponse(BaseModel):
    id: int
    client_id: int
    objective: str
    objective_label: str
    risk_profile: str
    risk_profile_label: str
    risk_profile_description: str
    score: int
    answers: dict[str, str]
    recommendation: SuitabilityRecommendation
    status: Literal["pending_review", "approved", "rejected", "superseded"]
    created_at: datetime
    expires_at: datetime
    reviewed_at: datetime | None
    reviewed_by_user_id: int | None


class SuitabilityReviewUpdate(BaseModel):
    approved: bool

