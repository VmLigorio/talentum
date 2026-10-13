# Talentum — backend/app/schemas/suitability.py
# Responsabilidade: Define os contratos públicos do questionário, da avaliação e da carteira modelo.
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SuitabilityOption(BaseModel):
    """Alternativa selecionável apresentada em uma pergunta do suitability."""

    value: str
    label: str


class SuitabilityQuestion(BaseModel):
    """Pergunta e formato de seleção enviados ao cliente."""

    key: str
    label: str
    description: str
    selection_mode: Literal["single", "multiple"] = "single"
    options: list[SuitabilityOption]


class SuitabilityQuestionnaireResponse(BaseModel):
    """Questionário, objetivos e contexto financeiro exibidos ao cliente."""

    objectives: list[dict[str, str]]
    questions: list[SuitabilityQuestion]
    financial_situation: "SuitabilityFinancialSituation"
    disclaimer: str


class SuitabilityFinancialCategory(BaseModel):
    """Valor patrimonial totalizado para uma categoria de bens."""

    category: str
    value: str


class SuitabilityFinancialGoal(BaseModel):
    """Meta financeira ativa usada como contexto da avaliação."""

    title: str
    target_value: str
    current_value: str
    target_date: str | None


class SuitabilityFinancialSituation(BaseModel):
    """Retrato financeiro confirmado ou apresentado durante a avaliação.

    A versão e a data do retrato permitem detectar alterações nos dados antes
    de registrar as respostas do questionário.
    """

    data_version: str
    snapshot_at: datetime
    has_financial_profile: bool
    financial_profile_updated_at: datetime | None
    monthly_income: str | None
    monthly_expenses: str | None
    monthly_surplus: str | None
    patrimony_total: str
    patrimony_by_category: list[SuitabilityFinancialCategory]
    patrimony_items_count: int
    active_goals: list[SuitabilityFinancialGoal]
    capacity_flags: list[str]
    client_confirmed_at: datetime | None = None


class SuitabilityAssessmentCreate(BaseModel):
    """Respostas do cliente e confirmação dos dados financeiros atuais."""

    objective: Literal["longevity", "dividends", "long_term", "short_term"]
    answers: dict[str, str] = Field(min_length=12, max_length=12)
    financial_data_version: str = Field(min_length=64, max_length=64)
    confirm_financial_situation: bool


class SuitabilityAdvisorAsset(BaseModel):
    """Ativo específico selecionado pelo assessor para uma proposta."""

    symbol: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=160)
    market: Literal["br", "global"]
    asset_type: str | None = Field(default=None, max_length=80)
    currency: str | None = Field(default=None, max_length=10)


class SuitabilityAllocation(BaseModel):
    """Percentual recomendado para uma classe e seus ativos ou subdivisões."""

    asset_class: str
    label: str
    percentage: int = Field(ge=0, le=100)
    rationale: str
    suballocations: list["SuitabilitySuballocation"] = Field(default_factory=list)
    advisor_assets: list[SuitabilityAdvisorAsset] = Field(default_factory=list)


class SuitabilityAdvisorAllocationUpdate(BaseModel):
    """Ativos escolhidos pelo assessor para uma classe da carteira modelo."""

    asset_class: str = Field(min_length=1, max_length=80)
    assets: list[SuitabilityAdvisorAsset] = Field(max_length=20)


class SuitabilityAdvisorProposalUpdate(BaseModel):
    """Conjunto de classes e ativos que o assessor pretende propor."""

    allocations: list[SuitabilityAdvisorAllocationUpdate] = Field(min_length=1, max_length=20)


class SuitabilitySuballocation(BaseModel):
    """Divisão interna de uma classe de ativos na recomendação."""

    asset_class: str
    label: str
    percentage: int = Field(ge=0, le=100)
    examples: list[str] = Field(default_factory=list)
    rationale: str


class SuitabilityRecommendedAction(BaseModel):
    """Ação prática sugerida junto à recomendação de carteira."""

    key: str
    title: str
    detail: str


class SuitabilityRecommendation(BaseModel):
    """Carteira sugerida, justificativas, alertas e orientações de uso."""

    title: str
    summary: str
    allocations: list[SuitabilityAllocation]
    financial_review_flags: list[str] = Field(default_factory=list)
    knowledge_review_flags: list[str] = Field(default_factory=list)
    recommended_actions: list[SuitabilityRecommendedAction] = Field(default_factory=list)
    guardrails: list[str]
    model_version: str = "1"
    advisor_proposal_published_at: datetime | None = None
    advisor_proposal_by: str | None = None


class SuitabilityAssessmentResponse(BaseModel):
    """Avaliação completa, estado de revisão e resposta do cliente."""

    id: int
    client_id: int
    objective: str
    objective_label: str
    risk_profile: str
    risk_profile_label: str
    risk_profile_description: str
    score: int
    answers: dict[str, str]
    financial_situation: SuitabilityFinancialSituation | None = None
    recommendation: SuitabilityRecommendation
    status: Literal["pending_review", "approved", "rejected", "superseded"]
    client_response: Literal["pending", "accepted", "declined", "adjustment_requested"]
    client_response_note: str | None
    client_response_at: datetime | None
    created_at: datetime
    expires_at: datetime
    reviewed_at: datetime | None
    reviewed_by_user_id: int | None


class SuitabilityReviewUpdate(BaseModel):
    """Decisão do assessor ao revisar uma avaliação pendente."""

    approved: bool


class SuitabilityClientResponseUpdate(BaseModel):
    """Aceite, recusa ou pedido de ajuste enviado pelo cliente."""

    response: Literal["accepted", "declined", "adjustment_requested"]
    note: str | None = Field(default=None, max_length=1000)
