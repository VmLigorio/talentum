# Talentum — backend/app/schemas/market_alert.py
# Responsabilidade: Define os schemas de entrada e saída usados pela validação e documentação da API.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MarketAlertCondition = Literal["at_or_below", "at_or_above"]
MarketAlertStatus = Literal["active", "paused", "triggered", "cancelled"]


class MarketAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    client_name: str
    created_by_user_id: int
    symbol: str
    market: Literal["br", "global"]
    target_price: float
    condition: MarketAlertCondition
    status: MarketAlertStatus
    last_price: float | None
    triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MarketAlertCreate(BaseModel):
    client_id: int | None = Field(default=None, ge=1)
    symbol: str = Field(min_length=1, max_length=32)
    market: Literal["br", "global"]
    target_price: float = Field(gt=0)
    condition: MarketAlertCondition = "at_or_below"


class MarketAlertUpdate(BaseModel):
    target_price: float | None = Field(default=None, gt=0)
    condition: MarketAlertCondition | None = None
    status: MarketAlertStatus | None = None
