from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InvestmentAllocation(BaseModel):
    market: Literal["br", "global"]
    label: str
    currency: str
    value: Decimal
    percentage: Decimal


class InvestmentCurrencyTotal(BaseModel):
    currency: str
    invested_total: Decimal
    current_total: Decimal
    pnl_total: Decimal
    pnl_percent: Decimal | None
    position_count: int


class InvestmentPositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    symbol: str
    market: Literal["br", "global"]
    quantity: Decimal
    average_price: Decimal
    institution: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    name: str | None = None
    current_price: Decimal | None = None
    currency: str | None = None
    source: str | None = None
    invested_value: Decimal
    current_value: Decimal | None = None
    pnl: Decimal | None = None
    pnl_percent: Decimal | None = None
    allocation_percent: Decimal = Decimal("0")


class InvestmentPositionCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    market: Literal["br", "global"]
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    average_price: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    institution: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=500)


class InvestmentPositionUpdate(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=8)
    average_price: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=8)
    institution: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=500)


class InvestmentPortfolioResponse(BaseModel):
    client_id: int
    invested_total: Decimal | None
    current_total: Decimal | None
    priced_invested_total: Decimal | None
    pnl_total: Decimal | None
    pnl_percent: Decimal | None
    total_currency: str | None
    mixed_currency: bool
    currency_totals: list[InvestmentCurrencyTotal]
    position_count: int
    priced_position_count: int
    unpriced_position_count: int
    allocations: list[InvestmentAllocation]
    positions: list[InvestmentPositionResponse]
