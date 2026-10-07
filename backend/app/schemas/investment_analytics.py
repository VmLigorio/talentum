# Talentum — backend/app/schemas/investment_analytics.py
# Responsabilidade: Define os schemas de entrada e saída usados pela validação e documentação da API.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class InvestmentAnalyticsPosition(BaseModel):
    id: int
    symbol: str
    market: Literal["br", "global"]
    currency: str
    invested_value: Decimal
    current_value: Decimal | None
    allocation_percent: Decimal
    period_return_percent: Decimal | None
    contribution_percent: Decimal | None
    data_available: bool


class InvestmentAnalyticsCurrencySummary(BaseModel):
    currency: str
    invested_total: Decimal
    priced_position_count: int
    portfolio_return_percent: Decimal | None
    top_concentration_percent: Decimal


class InvestmentBenchmark(BaseModel):
    market: Literal["br", "global"]
    symbol: str
    label: str
    return_percent: Decimal | None
    data_available: bool


class InvestmentAnalyticsResponse(BaseModel):
    client_id: int
    period: Literal["1mo", "3mo", "6mo", "1y", "5y"]
    generated_at: datetime
    position_count: int
    historical_position_count: int
    risk_flags: list[str]
    currency_summaries: list[InvestmentAnalyticsCurrencySummary]
    benchmarks: list[InvestmentBenchmark]
    positions: list[InvestmentAnalyticsPosition]
