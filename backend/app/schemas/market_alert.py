# Talentum — backend/app/schemas/market_alert.py
# Responsabilidade: Define os schemas de entrada e saída usados pela validação e documentação da API.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MarketAlertCondition = Literal["at_or_below", "at_or_above"]
MarketAlertStatus = Literal["active", "paused", "triggered", "cancelled"]


class MarketAlertResponse(BaseModel):
    """Condição de preço monitorada e seu estado atual."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    client_name: str
    created_by_user_id: int
    symbol: str
    # A resposta expõe o mercado sem informar a moeda da cotação.
    market: Literal["br", "global"]
    target_price: float
    condition: MarketAlertCondition
    status: MarketAlertStatus
    last_price: float | None
    triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MarketAlertCreate(BaseModel):
    """Parâmetros validados para criar um alerta de preço."""

    client_id: int | None = Field(default=None, ge=1)
    symbol: str = Field(min_length=1, max_length=32)
    market: Literal["br", "global"]
    target_price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    condition: MarketAlertCondition = "at_or_below"


class MarketAlertUpdate(BaseModel):
    """Campos permitidos para editar ou reativar um alerta."""

    # Os defaults permitem omitir campos, mas a união com None também aceita null explícito.
    target_price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    condition: MarketAlertCondition | None = None
    # Inclui estados normalmente produzidos pelo monitoramento/cancelamento (achado 191).
    status: MarketAlertStatus | None = None
