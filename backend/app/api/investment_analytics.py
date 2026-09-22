from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.investment_positions import _find_client, _load_positions, _quote
from app.db.database import get_db
from app.models import User
from app.schemas.investment_analytics import (
    InvestmentAnalyticsCurrencySummary,
    InvestmentAnalyticsPosition,
    InvestmentAnalyticsResponse,
    InvestmentBenchmark,
)
from app.schemas.market import MarketPeriod
from app.services.authorization import require_client_manager
from app.services.market_data import MarketDataService


router = APIRouter(prefix="/clients", tags=["investment-analytics"])
CENT = Decimal("0.01")


def _historical_return(service: MarketDataService, symbol: str, market: str, period: MarketPeriod) -> Decimal | None:
    try:
        history = service.history(symbol, market, period)
    except (httpx.HTTPError, ValueError):
        return None
    points = [point for point in history.points if point.close is not None]
    if len(points) < 2 or not points[0].close:
        return None
    return ((Decimal(str(points[-1].close)) / Decimal(str(points[0].close)) - 1) * 100).quantize(CENT, rounding=ROUND_HALF_UP)


@router.get("/{client_id}/investment-analytics", response_model=InvestmentAnalyticsResponse)
def investment_analytics(
    client_id: int,
    period: MarketPeriod = Query(default="1y"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestmentAnalyticsResponse:
    _find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    items = _load_positions(client_id, db)
    service = MarketDataService()
    raw: list[dict] = []
    invested_by_currency: dict[str, Decimal] = {}
    current_by_currency: dict[str, Decimal] = {}
    for item in items:
        _, current_price, quote_currency, _ = _quote(item, service)
        currency = quote_currency or ("BRL" if item.market == "br" else "USD")
        invested = item.quantity * item.average_price
        current = item.quantity * current_price if current_price is not None else None
        invested_by_currency[currency] = invested_by_currency.get(currency, Decimal("0")) + invested
        if current is not None:
            current_by_currency[currency] = current_by_currency.get(currency, Decimal("0")) + current
        raw.append({"item": item, "currency": currency, "invested": invested, "current": current})

    positions: list[InvestmentAnalyticsPosition] = []
    summary_acc: dict[str, dict[str, Decimal | int]] = {}
    for entry in raw:
        item = entry["item"]
        currency = entry["currency"]
        invested = entry["invested"]
        current = entry["current"]
        period_return = _historical_return(service, item.symbol, item.market, period)
        allocation = (current / current_by_currency[currency] * 100).quantize(CENT, rounding=ROUND_HALF_UP) if current is not None and current_by_currency.get(currency) else Decimal("0")
        contribution = (period_return * (invested / invested_by_currency[currency]) if period_return is not None and invested_by_currency.get(currency) else None)
        if contribution is not None:
            contribution = contribution.quantize(CENT, rounding=ROUND_HALF_UP)
        summary = summary_acc.setdefault(currency, {"invested": Decimal("0"), "weighted_return": Decimal("0"), "priced_count": 0, "top": Decimal("0")})
        summary["invested"] += invested
        if period_return is not None:
            summary["weighted_return"] += contribution or Decimal("0")
            summary["priced_count"] += 1
        summary["top"] = max(summary["top"], allocation)
        positions.append(InvestmentAnalyticsPosition(id=item.id, symbol=item.symbol, market=item.market, currency=currency, invested_value=invested, current_value=current, allocation_percent=allocation, period_return_percent=period_return, contribution_percent=contribution, data_available=period_return is not None))

    summaries = [InvestmentAnalyticsCurrencySummary(currency=currency, invested_total=data["invested"], priced_position_count=data["priced_count"], portfolio_return_percent=data["weighted_return"].quantize(CENT, rounding=ROUND_HALF_UP) if data["priced_count"] else None, top_concentration_percent=data["top"]) for currency, data in sorted(summary_acc.items())]
    benchmarks: list[InvestmentBenchmark] = []
    markets = {item.market for item in items}
    for market, symbol, label in [("br", "^BVSP", "Ibovespa"), ("global", "^GSPC", "S&P 500")]:
        if market in markets:
            result = _historical_return(service, symbol, market, period)
            benchmarks.append(InvestmentBenchmark(market=market, symbol=symbol, label=label, return_percent=result, data_available=result is not None))
    risk_flags: list[str] = []
    if any(entry["current"] is None for entry in raw):
        risk_flags.append("Existem posições sem cotação atual disponível.")
    if any(summary.top_concentration_percent > 40 for summary in summaries):
        risk_flags.append("Existe concentração superior a 40% em uma posição dentro de uma moeda.")
    if len({entry["currency"] for entry in raw}) > 1:
        risk_flags.append("A carteira possui mais de uma moeda; os resultados foram mantidos separados, sem conversão cambial.")
    return InvestmentAnalyticsResponse(client_id=client_id, period=period, generated_at=datetime.now(timezone.utc), position_count=len(items), historical_position_count=sum(position.data_available for position in positions), risk_flags=risk_flags, currency_summaries=summaries, benchmarks=benchmarks, positions=positions)
