# Talentum — backend/app/api/investment_monthly_performance.py
# Responsabilidade: Consolida os snapshots do mês e compara o resultado com o CDI oficial.
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from threading import Lock
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.investment_positions import _find_client
from app.db.database import get_db
from app.models import PortfolioSnapshot, User
from app.schemas.investment_monthly_performance import (
    CurrencyMonthlyPerformance,
    InvestmentMonthlyPerformanceResponse,
    MonthlyPortfolioPoint,
)
from app.services.authorization import require_client_manager
from app.services.portfolio_snapshots import capture_client_snapshots


router = APIRouter(prefix="/clients", tags=["investment-performance"])
SAO_PAULO = ZoneInfo("America/Sao_Paulo")
BCB_CDI_DAILY_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"
CENT = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")
CDI_CACHE_TTL = timedelta(hours=1)
_cdi_lock = Lock()
_cdi_cache: dict[str, tuple[datetime, list[tuple[date, Decimal]]]] = {}


def _percent(value: Decimal) -> Decimal:
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _fetch_cdi_rates(month_key: str, start: date, end: date) -> tuple[list[tuple[date, Decimal]], str]:
    now = datetime.now(timezone.utc)
    with _cdi_lock:
        cached = _cdi_cache.get(month_key)
        if cached and now - cached[0] < CDI_CACHE_TTL:
            return cached[1], "current"
    try:
        response = httpx.get(
            BCB_CDI_DAILY_URL,
            params={
                "formato": "json",
                "dataInicial": start.strftime("%d/%m/%Y"),
                "dataFinal": end.strftime("%d/%m/%Y"),
            },
            timeout=8.0,
        )
        response.raise_for_status()
        data = response.json()
        rates = [
            (datetime.strptime(row["data"], "%d/%m/%Y").date(), Decimal(str(row["valor"]).replace(",", ".")))
            for row in data
            if row.get("valor") not in (None, "")
        ]
        rates.sort(key=lambda item: item[0])
        with _cdi_lock:
            _cdi_cache[month_key] = (now, rates)
        return rates, "current"
    except (httpx.HTTPError, ValueError, KeyError, TypeError, ArithmeticError, AttributeError):
        if cached:
            return cached[1], "cached"
        return [], "unavailable"


def _compound_cdi(
    rates: list[tuple[date, Decimal]],
    start: date,
    end: date,
    month_start: date,
) -> Decimal | None:
    # A snapshot on the prior month's final date is the opening balance; CDI starts on day one.
    first_cdi_day = month_start if start < month_start else start + timedelta(days=1)
    factor = Decimal("1")
    found = False
    for rate_date, daily_percent in rates:
        if first_cdi_day <= rate_date <= end:
            factor *= Decimal("1") + daily_percent / Decimal("100")
            found = True
    return _percent((factor - Decimal("1")) * Decimal("100")) if found else None


def _cdi_through(
    rates: list[tuple[date, Decimal]],
    start: date,
    through: date,
    month_start: date,
) -> Decimal | None:
    return _compound_cdi(rates, start, through, month_start)


@router.get(
    "/{client_id}/investment-monthly-performance",
    response_model=InvestmentMonthlyPerformanceResponse,
)
def investment_monthly_performance(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestmentMonthlyPerformanceResponse:
    _find_client(client_id, db)
    require_client_manager(client_id, current_user, db)

    now = datetime.now(timezone.utc)
    local_now = now.astimezone(SAO_PAULO)
    month_start = local_now.date().replace(day=1)
    month_start_utc = datetime.combine(month_start, time.min, tzinfo=SAO_PAULO).astimezone(timezone.utc)
    captured = capture_client_snapshots(client_id, db, captured_at=now)
    if captured:
        db.commit()
        for snapshot in captured:
            db.refresh(snapshot)

    snapshots = list(
        db.scalars(
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.client_id == client_id,
                PortfolioSnapshot.captured_at >= month_start_utc - timedelta(days=4),
                PortfolioSnapshot.captured_at <= now,
            )
            .order_by(PortfolioSnapshot.captured_at.asc())
        ).all()
    )
    month_key = local_now.strftime("%Y-%m")
    rates, cdi_status = _fetch_cdi_rates(month_key, month_start, local_now.date())
    cdi_as_of = rates[-1][0] if rates else None
    grouped: dict[str, list[PortfolioSnapshot]] = {}
    for snapshot in snapshots:
        grouped.setdefault(snapshot.currency, []).append(snapshot)

    currencies: list[CurrencyMonthlyPerformance] = []
    for currency, items in sorted(grouped.items()):
        before_month = [item for item in items if item.captured_at.astimezone(SAO_PAULO).date() < month_start]
        in_month = [item for item in items if item.captured_at.astimezone(SAO_PAULO).date() >= month_start]
        baseline = before_month[-1] if before_month else (in_month[0] if in_month else None)
        latest = in_month[-1] if in_month else None
        if baseline is None or latest is None:
            currencies.append(
                CurrencyMonthlyPerformance(
                    currency=currency,
                    invested_value=None,
                    starting_invested_value=None,
                    profit_value=None,
                    return_percent=None,
                    cdi_percent=None,
                    excess_percentage_points=None,
                    percent_of_cdi=None,
                    coverage_start=None,
                    full_month_to_date=False,
                    data_available=False,
                    source_status="insufficient",
                    points=[],
                )
            )
            continue

        baseline_date = baseline.captured_at.astimezone(SAO_PAULO).date()
        full_month = baseline_date < month_start
        baseline_current = Decimal(baseline.current_total)
        baseline_invested = Decimal(baseline.invested_total)
        base_profit = baseline_current - baseline_invested
        data_complete = baseline.source_status == "complete" and latest.source_status == "complete" and baseline_current > 0
        monthly_profit: Decimal | None = None
        monthly_return: Decimal | None = None
        cdi_percent: Decimal | None = None
        excess: Decimal | None = None
        percent_of_cdi: Decimal | None = None
        if data_complete and latest.id != baseline.id:
            monthly_profit = _percent((Decimal(latest.current_total) - Decimal(latest.invested_total)) - base_profit)
            monthly_return = _percent(monthly_profit / baseline_current * Decimal("100"))
            if currency == "BRL":
                cdi_percent = _compound_cdi(rates, baseline_date, local_now.date(), month_start)
                if cdi_percent is not None:
                    excess = _percent(monthly_return - cdi_percent)
                    if cdi_percent:
                        percent_of_cdi = _percent(monthly_return / cdi_percent * Decimal("100"))

        daily_last: dict[date, PortfolioSnapshot] = {}
        for snapshot in in_month:
            snapshot_date = snapshot.captured_at.astimezone(SAO_PAULO).date()
            daily_last[snapshot_date] = snapshot
        daily_snapshots = [baseline] + [daily_last[day] for day in sorted(daily_last) if daily_last[day].id != baseline.id]
        points: list[MonthlyPortfolioPoint] = []
        if data_complete and baseline_current > 0:
            for snapshot in daily_snapshots:
                current = Decimal(snapshot.current_total)
                invested = Decimal(snapshot.invested_total)
                profit = _percent((current - invested) - base_profit)
                return_percent = _percent(profit / baseline_current * Decimal("100"))
                cdi_to_date = (
                    _cdi_through(rates, baseline_date, snapshot.captured_at.astimezone(SAO_PAULO).date(), month_start)
                    if currency == "BRL"
                    else None
                )
                points.append(
                    MonthlyPortfolioPoint(
                        date=snapshot.captured_at.astimezone(SAO_PAULO).date(),
                        return_percent=return_percent,
                        cdi_return_percent=cdi_to_date,
                        profit_value=profit,
                        current_value=current,
                    )
                )

        currencies.append(
            CurrencyMonthlyPerformance(
                currency=currency,
                invested_value=Decimal(latest.invested_total),
                starting_invested_value=baseline_invested,
                profit_value=monthly_profit,
                return_percent=monthly_return,
                cdi_percent=cdi_percent,
                excess_percentage_points=excess,
                percent_of_cdi=percent_of_cdi,
                coverage_start=baseline_date,
                full_month_to_date=full_month,
                data_available=monthly_return is not None,
                source_status="complete" if data_complete else "partial",
                points=points,
            )
        )

    return InvestmentMonthlyPerformanceResponse(
        client_id=client_id,
        month=month_key,
        generated_at=now,
        cdi_as_of=cdi_as_of,
        cdi_source=BCB_CDI_DAILY_URL,
        cdi_status=cdi_status,
        currencies=currencies,
    )
