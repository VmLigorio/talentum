# Talentum — backend/app/schemas/market.py
# Responsabilidade: Define os schemas de entrada e saída usados pela validação e documentação da API.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


MarketRegion = Literal["all", "br", "global"]
MarketPeriod = Literal["1mo", "3mo", "6mo", "1y", "5y"]


class MarketReference(BaseModel):
    label: str
    url: str
    source: str


class FiiReportSummary(BaseModel):
    reference_date: datetime | None = None
    total_assets: float | None = None
    equity: float | None = None
    nav_per_share: float | None = None
    admin_fee_rate: float | None = None
    monthly_return: float | None = None
    monthly_patrimonial_return: float | None = None
    monthly_dividend_yield: float | None = None
    amortization_rate: float | None = None
    total_investors: float | None = None
    cash: float | None = None
    liquidity_needs: float | None = None
    government_bonds: float | None = None
    private_bonds: float | None = None
    fixed_income_funds: float | None = None
    total_invested: float | None = None
    real_estate_assets: float | None = None
    cri: float | None = None
    lci: float | None = None
    fii_holdings: float | None = None
    receivables: float | None = None
    total_liabilities: float | None = None


class MarketInstrument(BaseModel):
    market: Literal["br", "global"]
    symbol: str
    name: str
    exchange: str | None = None
    asset_type: str | None = None
    currency: str | None = None
    price: float | None = None
    change: float | None = None
    change_percent: float | None = None
    previous_close: float | None = None
    market_cap: float | None = None
    volume: float | None = None
    average_volume: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    dividend_yield: float | None = None
    dividend_yield_1m: float | None = None
    price_earnings: float | None = None
    price_to_book: float | None = None
    return_on_equity: float | None = None
    shares_outstanding: float | None = None
    total_investors: float | None = None
    nav_per_share: float | None = None
    equity: float | None = None
    total_assets: float | None = None
    sector: str | None = None
    subsector: str | None = None
    industry: str | None = None
    segment: str | None = None
    management_type: str | None = None
    as_of_date: datetime | None = None
    logo_url: str | None = None
    fii_report: FiiReportSummary | None = None
    references: list[MarketReference] = Field(default_factory=list)
    updated_at: datetime | None = None
    source: str


class MarketSearchResponse(BaseModel):
    query: str = Field(min_length=1)
    market: MarketRegion
    fetched_at: datetime
    results: list[MarketInstrument]
    warnings: list[str] = []


class MarketHistoryPoint(BaseModel):
    date: datetime
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: float | None = None
    return_percent: float | None = None


class MarketHistoryResponse(BaseModel):
    symbol: str
    market: Literal["br", "global"]
    period: MarketPeriod
    currency: str | None = None
    benchmark_symbol: str | None = None
    points: list[MarketHistoryPoint]
    benchmark_points: list[MarketHistoryPoint] = Field(default_factory=list)
    observation_count: int = 0
    average_volume: float | None = None
    annualized_volatility: float | None = None
    max_drawdown: float | None = None
    volatility_band: Literal["lower", "intermediate", "higher"] | None = None
    source: str
