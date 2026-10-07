# Talentum — backend/app/services/portfolio_snapshots.py
# Responsabilidade: Concentra regras de negócio e integrações reutilizáveis, mantendo as rotas mais simples.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.investment_positions import _portfolio
from app.models import PortfolioSnapshot, User


SNAPSHOT_DEDUPLICATION_WINDOW = timedelta(minutes=5)


def capture_client_snapshots(
    client_id: int,
    db: Session,
    captured_at: datetime | None = None,
) -> list[PortfolioSnapshot]:
    portfolio = _portfolio(client_id, db)
    if not portfolio.currency_totals:
        return []

    now = captured_at or datetime.now(timezone.utc)
    priced_by_currency: dict[str, int] = {}
    for position in portfolio.positions:
        if position.current_value is not None:
            priced_by_currency[position.currency or "BRL"] = priced_by_currency.get(position.currency or "BRL", 0) + 1

    snapshots: list[PortfolioSnapshot] = []
    for total in portfolio.currency_totals:
        latest = db.scalar(
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.client_id == client_id,
                PortfolioSnapshot.currency == total.currency,
            )
            .order_by(desc(PortfolioSnapshot.captured_at))
            .limit(1)
        )
        if latest and latest.captured_at and now - latest.captured_at < SNAPSHOT_DEDUPLICATION_WINDOW:
            continue
        priced_count = priced_by_currency.get(total.currency, 0)
        snapshots.append(
            PortfolioSnapshot(
                client_id=client_id,
                captured_at=now,
                currency=total.currency,
                invested_total=total.invested_total,
                current_total=total.current_total,
                pnl_total=total.pnl_total,
                position_count=total.position_count,
                priced_position_count=priced_count,
                source_status="complete" if priced_count == total.position_count else "partial",
            )
        )
    db.add_all(snapshots)
    return snapshots


def capture_all_portfolio_snapshots(db: Session) -> tuple[int, int, int]:
    client_ids = list(
        db.scalars(select(User.id).where(User.role == "client", User.is_active.is_(True))).all()
    )
    snapshots_created = 0
    failures = 0
    for client_id in client_ids:
        try:
            with db.begin_nested():
                snapshots_created += len(capture_client_snapshots(client_id, db))
        except Exception:
            failures += 1
    return len(client_ids), snapshots_created, failures
