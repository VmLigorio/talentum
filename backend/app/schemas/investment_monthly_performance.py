# Talentum — backend/app/schemas/investment_monthly_performance.py
# Responsabilidade: Define os dados de rendimento mensal e comparação com o CDI.
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class MonthlyPortfolioPoint(BaseModel):
    date: date
    return_percent: Decimal
    cdi_return_percent: Decimal | None
    profit_value: Decimal
    current_value: Decimal


class CurrencyMonthlyPerformance(BaseModel):
    currency: str
    invested_value: Decimal | None
    starting_invested_value: Decimal | None
    profit_value: Decimal | None
    return_percent: Decimal | None
    cdi_percent: Decimal | None
    excess_percentage_points: Decimal | None
    percent_of_cdi: Decimal | None
    coverage_start: date | None
    full_month_to_date: bool
    data_available: bool
    source_status: Literal["complete", "partial", "insufficient"]
    points: list[MonthlyPortfolioPoint]


class InvestmentMonthlyPerformanceResponse(BaseModel):
    client_id: int
    month: str
    generated_at: datetime
    cdi_as_of: date | None
    cdi_source: str
    cdi_status: Literal["current", "cached", "unavailable"]
    currencies: list[CurrencyMonthlyPerformance]
