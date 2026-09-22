from decimal import Decimal

from app.models import MarketAlert
from app.services.market_alerts import _price_reached


def test_market_alert_reaches_lower_target() -> None:
    alert = MarketAlert(target_price=Decimal("32.50"), condition="at_or_below")

    assert _price_reached(alert, 32.50) is True
    assert _price_reached(alert, 31.90) is True
    assert _price_reached(alert, 32.51) is False


def test_market_alert_reaches_upper_target() -> None:
    alert = MarketAlert(target_price=Decimal("180.00"), condition="at_or_above")

    assert _price_reached(alert, 180.00) is True
    assert _price_reached(alert, 181.20) is True
    assert _price_reached(alert, 179.99) is False
