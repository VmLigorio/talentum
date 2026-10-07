# Talentum — backend/app/schemas/investment_transaction.py
# Contratos de entrada e saída do histórico de compras e vendas.
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InvestmentTransactionCreate(BaseModel):
    operation_type: Literal["buy", "sell"]
    symbol: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=160)
    market: Literal["br", "global"]
    operation_date: date
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    unit_price: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    fees: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=2)
    institution: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=500)


class InvestmentTransactionVoid(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


class InvestmentTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    position_id: int | None
    created_by_user_id: int | None
    operation_type: Literal["buy", "sell"]
    symbol: str
    name: str | None
    market: Literal["br", "global"]
    currency: str
    operation_date: date
    quantity: Decimal
    unit_price: Decimal
    gross_value: Decimal
    fees: Decimal
    net_value: Decimal
    realized_pnl: Decimal | None
    quantity_before: Decimal
    average_price_before: Decimal | None
    quantity_after: Decimal
    average_price_after: Decimal | None
    institution: str | None
    notes: str | None
    voided_at: datetime | None
    voided_by_user_id: int | None
    void_reason: str | None
    created_at: datetime
