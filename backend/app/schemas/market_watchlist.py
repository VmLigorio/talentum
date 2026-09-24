# Talentum — backend/app/schemas/market_watchlist.py
# Responsabilidade: Define os schemas de entrada e saída usados pela validação e documentação da API.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MarketWatchlistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    client_name: str
    created_by_user_id: int
    symbol: str
    market: Literal["br", "global"]
    note: str | None
    name: str | None
    current_price: float | None
    currency: str | None
    source: str | None
    created_at: datetime
    updated_at: datetime


class MarketWatchlistCreate(BaseModel):
    client_id: int | None = Field(default=None, ge=1)
    symbol: str = Field(min_length=1, max_length=32)
    market: Literal["br", "global"]
    note: str | None = Field(default=None, max_length=500)
