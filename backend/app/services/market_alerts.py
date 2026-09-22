from datetime import datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ClientProfile, MarketAlert, User
from app.services.market_data import MarketDataService
from app.services.notifications import create_client_notification


def _price_reached(alert: MarketAlert, price: float) -> bool:
    target = float(alert.target_price)
    return price <= target if alert.condition == "at_or_below" else price >= target


def sync_market_alerts_for_client(client_id: int, db: Session) -> tuple[int, int, bool]:
    alerts = list(
        db.scalars(
            select(MarketAlert).where(
                MarketAlert.client_id == client_id,
                MarketAlert.status == "active",
            )
        ).all()
    )
    if not alerts:
        return 0, 0, False

    service = MarketDataService()
    checked = 0
    triggered = 0
    changed = False
    now = datetime.now(timezone.utc)
    for alert in alerts:
        try:
            instrument = service.details(alert.symbol, alert.market)
        except (httpx.HTTPError, ValueError):
            continue
        if instrument.price is None:
            continue
        checked += 1
        current_price = float(instrument.price)
        alert.last_price = Decimal(str(current_price))
        changed = True
        if not _price_reached(alert, current_price):
            continue

        alert.status = "triggered"
        alert.triggered_at = now
        triggered += 1
        changed = True
        direction = "atingiu ou caiu abaixo de" if alert.condition == "at_or_below" else "atingiu ou superou"
        create_client_notification(
            db,
            client_id=client_id,
            kind="market_price_alert",
            title=f"Alerta de preço: {alert.symbol}",
            message=(
                f"{alert.symbol} está em {current_price:.2f} e {direction} "
                f"o alvo de {float(alert.target_price):.2f}."
            ),
            dedupe_key=f"market-alert:{alert.id}:triggered:{alert.target_price}:{alert.condition}",
        )
    return checked, triggered, changed


def sync_market_alerts_for_user(user: User, db: Session) -> tuple[int, int, bool]:
    if user.role == "client":
        client_ids = [user.id]
    elif user.role == "advisor":
        client_ids = list(
            db.scalars(
                select(ClientProfile.user_id).where(ClientProfile.advisor_id == user.id)
            ).all()
        )
    else:
        client_ids = list(db.scalars(select(User.id).where(User.role == "client")).all())

    checked = 0
    triggered = 0
    changed = False
    for client_id in client_ids:
        current_checked, current_triggered, current_changed = sync_market_alerts_for_client(client_id, db)
        checked += current_checked
        triggered += current_triggered
        changed = changed or current_changed
    return checked, triggered, changed


def sync_all_market_alerts(db: Session) -> tuple[int, int, bool]:
    client_ids = list(
        db.scalars(
            select(MarketAlert.client_id)
            .where(MarketAlert.status == "active")
            .distinct()
        ).all()
    )
    checked = 0
    triggered = 0
    changed = False
    for client_id in client_ids:
        current_checked, current_triggered, current_changed = sync_market_alerts_for_client(client_id, db)
        checked += current_checked
        triggered += current_triggered
        changed = changed or current_changed
    return checked, triggered, changed
