# Talentum — backend/app/schemas/dashboard.py
# Responsabilidade: Define os schemas de entrada e saída usados pela validação e documentação da API.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CategoryTotal(BaseModel):
    """Total financeiro e participação de uma categoria patrimonial."""

    category: str
    total: Decimal
    percentage: Decimal


class GoalProgress(BaseModel):
    """Progresso calculado de uma meta apresentada no painel."""

    id: int
    title: str
    target_value: Decimal
    current_value: Decimal
    target_date: date | None
    percentage: Decimal
    status: str


class DashboardResponse(BaseModel):
    """Resumo financeiro do cliente usado para montar o painel inicial."""

    client_id: int
    patrimony_total: Decimal
    patrimony_by_category: list[CategoryTotal]
    goals: list[GoalProgress]
    monthly_income: Decimal | None = None
    monthly_expenses: Decimal | None = None
    action_pending: int = 0
    action_overdue: int = 0
