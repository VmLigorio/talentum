# Talentum — backend/app/schemas/portfolio_snapshot.py
# Responsabilidade: Define os schemas de entrada e saída usados pela validação e documentação da API.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PortfolioSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    captured_at: datetime
    currency: str
    invested_total: Decimal
    current_total: Decimal
    pnl_total: Decimal
    position_count: int
    priced_position_count: int
    source_status: str
