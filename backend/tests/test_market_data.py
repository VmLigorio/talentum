# Talentum — backend/tests/test_market_data.py
# Responsabilidade: Contém testes automatizados que protegem o comportamento esperado do sistema.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import timezone

from app.schemas.market import MarketHistoryPoint, MarketInstrument
from app.services.market_data import MarketDataService, _date, _history_summary, _number, _with_returns, clear_market_cache


class _FakeResponse:
    def __init__(self, payload: dict, success: bool = True) -> None:
        self._payload = payload
        self.is_success = success

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(self, url: str, **kwargs: object) -> _FakeResponse:
        self.calls.append((url, kwargs))
        return self.response


def test_market_data_normalizers() -> None:
    assert _number("12.5") == 12.5
    assert _number(True) is None
    assert _date(0).tzinfo == timezone.utc
    assert _date("not-a-date") is None


def test_brapi_quote_is_normalized() -> None:
    item = MarketDataService._brapi_item(
        {
            "symbol": "PETR4",
            "longName": "Petroleo Brasileiro SA",
            "currency": "BRL",
            "regularMarketPrice": 36.65,
            "regularMarketChangePercent": -0.95,
            "regularMarketVolume": 1000,
        }
    )

    assert isinstance(item, MarketInstrument)
    assert item.market == "br"
    assert item.symbol == "PETR4"
    assert item.price == 36.65
    assert item.change_percent == -0.95


def test_brapi_list_fields_are_normalized(monkeypatch) -> None:
    clear_market_cache()
    client = _FakeClient(
        _FakeResponse(
            {
                "stocks": [
                    {
                        "stock": "VALE3",
                        "name": "VALE3",
                        "close": 52.89,
                        "change": -1.23,
                        "change_abs": -0.65,
                        "volume": 1000,
                        "market_cap": 229000000000,
                        "type": "stock",
                    }
                ]
            }
        )
    )
    monkeypatch.setattr("app.services.market_data.httpx.Client", lambda **kwargs: client)

    results = MarketDataService()._search_brazil("VALE3")

    assert results[0].symbol == "VALE3"
    assert results[0].price == 52.89
    assert results[0].change == -0.65
    assert results[0].change_percent == -1.23
    assert client.calls[1][1]["params"] == {"search": "VALE3", "limit": 15}


def test_repeated_search_uses_short_lived_cache(monkeypatch) -> None:
    clear_market_cache()
    client = _FakeClient(_FakeResponse({"stocks": [{"stock": "QUAL3", "name": "QUAL3", "close": 8.2}]}))
    monkeypatch.setattr("app.services.market_data.httpx.Client", lambda **kwargs: client)

    service = MarketDataService()
    first = service.search("QUAL3", "br")
    second = service.search("QUAL3", "br")

    assert first == second
    assert len(client.calls) == 2


def test_ibovespa_alias_uses_bvsp(monkeypatch) -> None:
    client = _FakeClient(
        _FakeResponse(
            {
                "results": [
                    {
                        "symbol": "^BVSP",
                        "longName": "IBOVESPA",
                        "regularMarketPrice": 125000,
                    }
                ]
            }
        )
    )
    monkeypatch.setattr("app.services.market_data.httpx.Client", lambda **kwargs: client)

    results = MarketDataService()._search_brazil("IBOVESPA")

    assert results[0].symbol == "^BVSP"
    assert "%5EBVSP" in client.calls[0][0]


def test_fii_indicators_are_normalized() -> None:
    base = MarketInstrument(
        market="br",
        symbol="MXRF11",
        name="MXRF11",
        exchange="B3",
        asset_type="fund",
        currency="BRL",
        source="brapi",
    )

    result = MarketDataService._merge_fii_details(
        base,
        {
            "name": "FII MAXI RENDA RL",
            "price": 9.58,
            "dividendYield12m": 0.12381,
            "dividendYield1m": 0.009328,
            "priceToNav": 1.018,
            "navPerShare": 9.41,
            "totalInvestors": 1357621,
            "sharesOutstanding": 460269540,
            "equity": 4331102700,
            "segmentoAtuacao": "Logística",
            "tipoGestao": "Ativa",
        },
    )

    assert result.name == "FII MAXI RENDA RL"
    assert result.dividend_yield == 0.12381
    assert result.dividend_yield_1m == 0.009328
    assert result.price_to_book == 1.018
    assert result.total_investors == 1357621
    assert result.shares_outstanding == 460269540
    assert result.segment == "Logística"


def test_history_points_calculate_normalized_return() -> None:
    points = [
        MarketHistoryPoint(date=_date(1) or _date(0), close=100),
        MarketHistoryPoint(date=_date(2) or _date(0), close=110),
        MarketHistoryPoint(date=_date(3) or _date(0), close=95),
    ]

    result = _with_returns(points)

    assert result[0].return_percent == 0
    assert result[1].return_percent == 10
    assert result[2].return_percent == -5


def test_brazil_history_uses_yahoo_symbol_fallback() -> None:
    assert MarketDataService._yahoo_symbol_for_brazil("PETR4") == "PETR4.SA"
    assert MarketDataService._yahoo_symbol_for_brazil("MXRF11") == "MXRF11.SA"
    assert MarketDataService._yahoo_symbol_for_brazil("^BVSP") == "^BVSP"


def test_history_summary_reports_volatility_and_drawdown() -> None:
    points = [
        MarketHistoryPoint(date=_date(1) or _date(0), close=100, volume=10),
        MarketHistoryPoint(date=_date(2) or _date(0), close=120, volume=20),
        MarketHistoryPoint(date=_date(3) or _date(0), close=90, volume=30),
    ]

    summary = _history_summary(points)

    assert summary["observation_count"] == 3
    assert summary["average_volume"] == 20
    assert summary["max_drawdown"] == -25
    assert summary["annualized_volatility"] is not None
