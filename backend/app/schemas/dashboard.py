from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CategoryTotal(BaseModel):
    category: str
    total: Decimal
    percentage: Decimal


class GoalProgress(BaseModel):
    id: int
    title: str
    target_value: Decimal
    current_value: Decimal
    target_date: date | None
    percentage: Decimal
    status: str


class DashboardResponse(BaseModel):
    client_id: int
    patrimony_total: Decimal
    patrimony_by_category: list[CategoryTotal]
    goals: list[GoalProgress]
    monthly_income: Decimal | None = None
    monthly_expenses: Decimal | None = None
    action_pending: int = 0
    action_overdue: int = 0
