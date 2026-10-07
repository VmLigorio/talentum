# Talentum — backend/tests/test_market_alerts.py
# Responsabilidade: Contém testes automatizados que protegem o comportamento esperado do sistema.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import MarketAlert
from app.schemas.market_alert import MarketAlertCreate, MarketAlertUpdate
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


def test_market_alert_inputs_accept_two_decimal_places() -> None:
    create = MarketAlertCreate(
        symbol="PETR4", market="br", target_price="32.50"
    )
    update = MarketAlertUpdate(target_price="32.50")

    assert create.target_price == Decimal("32.50")
    assert update.target_price == Decimal("32.50")


def test_market_alert_inputs_reject_more_than_two_decimal_places() -> None:
    with pytest.raises(ValidationError):
        MarketAlertCreate(symbol="PETR4", market="br", target_price="32.501")

    with pytest.raises(ValidationError):
        MarketAlertUpdate(target_price="32.501")
