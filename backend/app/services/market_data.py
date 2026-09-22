from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings
from app.schemas.market import (
    FiiReportSummary,
    MarketHistoryPoint,
    MarketHistoryResponse,
    MarketInstrument,
    MarketPeriod,
    MarketReference,
    MarketRegion,
)


class _MarketCache:
    """Small process-local cache that reduces provider pressure during repeated UI queries."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, ...], tuple[float, Any]] = {}
        self._lock = RLock()

    def get(self, key: tuple[str, ...]) -> Any | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= monotonic():
                self._items.pop(key, None)
                return None
            return value

    def set(self, key: tuple[str, ...], value: Any, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        with self._lock:
            self._items[key] = (monotonic() + ttl_seconds, value)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_market_cache = _MarketCache()


def clear_market_cache() -> None:
    """Clear cached provider responses, primarily for tests and controlled refreshes."""

    _market_cache.clear()


class MarketDataService:
    """Small provider adapter used by the Advisor/Adm research screen."""

    def __init__(self) -> None:
        settings = get_settings()
        self.brapi_base_url = settings.brapi_base_url.rstrip("/")
        self.brapi_token = settings.brapi_token
        self.yahoo_base_url = settings.yahoo_finance_base_url.rstrip("/")
        self.timeout = settings.market_data_timeout_seconds
        self.retry_attempts = settings.market_retry_attempts
        self.cache_ttl_seconds = settings.market_cache_ttl_seconds

    def search(self, query: str, market: MarketRegion) -> tuple[list[MarketInstrument], list[str]]:
        normalized_query = query.strip().casefold()
        cache_key = ("search", market, normalized_query)
        cached = _market_cache.get(cache_key)
        if cached is not None:
            return cached

        results: list[MarketInstrument] = []
        warnings: list[str] = []
        if market in ("all", "br"):
            try:
                results.extend(self._search_brazil(query))
            except (httpx.HTTPError, ValueError) as exc:
                warnings.append(f"B3 indisponível no momento: {self._safe_error(exc)}")
        if market in ("all", "global"):
            try:
                results.extend(self._search_global(query))
            except (httpx.HTTPError, ValueError) as exc:
                warnings.append(f"Mercado internacional indisponível no momento: {self._safe_error(exc)}")

        unique: dict[tuple[str, str], MarketInstrument] = {}
        for item in results:
            unique[(item.market, item.symbol.upper())] = item
        value = (list(unique.values())[:30], warnings)
        if not warnings:
            _market_cache.set(cache_key, value, self.cache_ttl_seconds)
        return value

    def details(self, symbol: str, market: MarketRegion) -> MarketInstrument:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("Informe um símbolo válido")
        cache_key = ("details", market, normalized)
        cached = _market_cache.get(cache_key)
        if cached is not None:
            return cached
        if market == "br":
            result = self._brazil_details(normalized)
        elif market == "global":
            result = self._global_details(normalized)
        else:
            raise ValueError("O detalhamento precisa indicar um mercado")
        _market_cache.set(cache_key, result, self.cache_ttl_seconds)
        return result

    def history(self, symbol: str, market: MarketRegion, period: MarketPeriod) -> MarketHistoryResponse:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("Informe um símbolo válido")
        cache_key = ("history", market, normalized, period)
        cached = _market_cache.get(cache_key)
        if cached is not None:
            return cached
        if market == "br":
            result = self._brazil_history(normalized, period)
        elif market == "global":
            result = self._global_history(normalized, period)
        else:
            raise ValueError("O histórico precisa indicar um mercado")
        _market_cache.set(cache_key, result, self.cache_ttl_seconds)
        return result

    def _client(self) -> httpx.Client:
        headers = {"Accept": "application/json", "User-Agent": "Talentum/0.1"}
        if self.brapi_token:
            headers["Authorization"] = f"Bearer {self.brapi_token}"
        return httpx.Client(
            timeout=self.timeout,
            headers=headers,
            follow_redirects=True,
            transport=httpx.HTTPTransport(retries=self.retry_attempts),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        )

    def _search_brazil(self, query: str) -> list[MarketInstrument]:
        normalized = query.strip().upper()
        if not normalized:
            return []
        quote_symbol = {
            "IBOV": "^BVSP",
            "IBOVESPA": "^BVSP",
            "^BVSP": "^BVSP",
        }.get(normalized, normalized)
        # The quote endpoint is reliable for an exact B3 ticker and also works
        # without a token for the public examples supported by Brapi.
        if " " not in normalized and len(normalized) <= 12:
            with self._client() as client:
                response = client.get(f"{self.brapi_base_url}/api/quote/{quote(quote_symbol, safe=',')}")
                if response.is_success:
                    payload = response.json()
                    results = [
                        self._brapi_item(item)
                        for item in payload.get("results", [])
                        if isinstance(item, dict)
                    ]
                    if results:
                        return results

        # Brapi's list endpoint is used for name/ticker discovery. Ask the
        # provider to filter the complete B3 universe instead of only reading
        # its first page. The current response uses stock/name/close/change.
        with self._client() as client:
            response = client.get(
                f"{self.brapi_base_url}/api/quote/list",
                params={"search": normalized, "limit": 15},
            )
            response.raise_for_status()
            payload = response.json()
        if isinstance(payload, list):
            candidates = payload
        else:
            candidates = [
                *payload.get("stocks", []),
                *payload.get("indexes", []),
                *payload.get("results", []),
            ]
        needle = normalized.casefold()
        return [
            self._brapi_item(item)
            for item in candidates
            if isinstance(item, dict)
            and needle in " ".join(
                str(item.get(key, ""))
                for key in ("stock", "symbol", "name", "shortName", "longName")
            ).casefold()
        ][:15]

    def _brazil_details(self, symbol: str) -> MarketInstrument:
        quote_symbol = {"IBOV": "^BVSP", "IBOVESPA": "^BVSP"}.get(symbol, symbol)
        with self._client() as client:
            response = client.get(
                f"{self.brapi_base_url}/api/quote/{quote(quote_symbol, safe=',')}",
                params={"modules": "defaultKeyStatistics,summaryProfile"},
            )
            item: MarketInstrument | None = None
            last_response = response
            if response.is_success:
                payload = response.json()
                results = [entry for entry in payload.get("results", []) if isinstance(entry, dict)]
                if results:
                    item = self._brapi_item(results[0])

            # Some Brapi plans expose the quote but restrict optional modules.
            # Keep the detail screen useful with the basic quote in that case.
            if item is None:
                basic_response = client.get(
                    f"{self.brapi_base_url}/api/quote/{quote(quote_symbol, safe=',')}"
                )
                last_response = basic_response
                if basic_response.is_success:
                    basic_payload = basic_response.json()
                    basic_results = [entry for entry in basic_payload.get("results", []) if isinstance(entry, dict)]
                    if basic_results:
                        item = self._brapi_item(basic_results[0])

            # FIIs have a dedicated endpoint with indicators that are not
            # present in the generic quote response.
            if symbol.endswith("11") and symbol not in {"^BVSP"}:
                fii_response = client.get(
                    f"{self.brapi_base_url}/api/v2/fii/indicators",
                    params={"symbols": symbol},
                )
                if fii_response.is_success:
                    fii_payload = fii_response.json()
                    fii_items = [entry for entry in fii_payload.get("fiis", []) if isinstance(entry, dict)]
                    if fii_items:
                        fii_item = fii_items[0]
                        if item is None:
                            item = self._brapi_item({
                                "symbol": symbol,
                                "name": fii_item.get("name") or symbol,
                                "type": "fund",
                                "price": fii_item.get("price"),
                            })
                        item = self._merge_fii_details(item, fii_item)
                        report = self._load_fii_report(client, symbol)
                        references = [
                            MarketReference(
                                label="Informe mensal estruturado do FII",
                                url="https://dados.cvm.gov.br/dataset/fii-doc-inf_mensal",
                                source="CVM",
                            ),
                            MarketReference(
                                label="Consulta pública de fundos da CVM",
                                url="https://cvmweb.cvm.gov.br/SWB/Sistemas/SCW/CPublica/CPublica.asp?SemFrames=True",
                                source="CVM",
                            ),
                        ]
                        item = item.model_copy(update={"fii_report": report, "references": references})
            if item is None:
                if not last_response.is_success:
                    last_response.raise_for_status()
                raise ValueError(f"Ativo {symbol} não encontrado")
            return item

    def _global_details(self, symbol: str) -> MarketInstrument:
        with self._client() as client:
            response = client.get(
                f"{self.yahoo_base_url}/v1/finance/search",
                params={"q": symbol, "quotesCount": 15, "newsCount": 0, "enableFuzzyQuery": "true"},
            )
            response.raise_for_status()
            payload = response.json()
            quotes = [item for item in payload.get("quotes", []) if isinstance(item, dict)]
            match = next((item for item in quotes if str(item.get("symbol", "")).upper() == symbol), quotes[0] if quotes else None)
            if not match:
                raise ValueError(f"Ativo {symbol} não encontrado")
            return self._enrich_yahoo_item(client, match)

    def _brazil_history(self, symbol: str, period: MarketPeriod) -> MarketHistoryResponse:
        quote_symbol = {"IBOV": "^BVSP", "IBOVESPA": "^BVSP"}.get(symbol, symbol)
        with self._client() as client:
            source = "brapi"
            try:
                points, currency = self._fetch_brapi_history(client, quote_symbol, period)
                if not points:
                    raise ValueError("Brapi não retornou pontos históricos")
            except (httpx.HTTPError, ValueError):
                points, currency = self._fetch_yahoo_history(client, self._yahoo_symbol_for_brazil(quote_symbol), period)
                source = "yahoo_finance"
            if not points:
                raise ValueError(f"Histórico de {symbol} não encontrado")
            benchmark_points: list[MarketHistoryPoint] = []
            try:
                benchmark_points, _ = self._fetch_brapi_history(client, "^BVSP", period)
            except (httpx.HTTPError, ValueError):
                try:
                    benchmark_points, _ = self._fetch_yahoo_history(client, "^BVSP", period)
                except (httpx.HTTPError, ValueError):
                    pass
        return MarketHistoryResponse(
            symbol=symbol,
            market="br",
            period=period,
            currency=currency or "BRL",
            benchmark_symbol="^BVSP" if quote_symbol != "^BVSP" else None,
            points=_with_returns(points),
            benchmark_points=_with_returns(benchmark_points),
            **_history_summary(points),
            source=source,
        )

    @staticmethod
    def _yahoo_symbol_for_brazil(symbol: str) -> str:
        if symbol.startswith("^") or symbol.endswith(".SA"):
            return symbol
        return f"{symbol}.SA"

    def _global_history(self, symbol: str, period: MarketPeriod) -> MarketHistoryResponse:
        with self._client() as client:
            points, currency = self._fetch_yahoo_history(client, symbol, period)
            if not points:
                raise ValueError(f"Histórico de {symbol} não encontrado")
            benchmark_points: list[MarketHistoryPoint] = []
            try:
                benchmark_points, _ = self._fetch_yahoo_history(client, "^GSPC", period)
            except (httpx.HTTPError, ValueError):
                pass
        return MarketHistoryResponse(
            symbol=symbol,
            market="global",
            period=period,
            currency=currency,
            benchmark_symbol="^GSPC",
            points=_with_returns(points),
            benchmark_points=_with_returns(benchmark_points),
            **_history_summary(points),
            source="yahoo_finance",
        )

    def _fetch_brapi_history(
        self,
        client: httpx.Client,
        symbol: str,
        period: MarketPeriod,
    ) -> tuple[list[MarketHistoryPoint], str | None]:
        response = client.get(
            f"{self.brapi_base_url}/api/quote/{quote(symbol, safe=',')}",
            params={"range": period, "interval": "1d"},
        )
        response.raise_for_status()
        payload = response.json()
        results = [entry for entry in payload.get("results", []) if isinstance(entry, dict)]
        if not results:
            return [], None
        item = results[0]
        data = item.get("data") if isinstance(item.get("data"), dict) else item
        rows = data.get("historicalDataPrice", [])
        points = [
            MarketHistoryPoint(
                date=timestamp,
                open=_number(row.get("open")),
                high=_number(row.get("high")),
                low=_number(row.get("low")),
                close=close,
                volume=_number(row.get("volume")),
            )
            for row in rows
            if isinstance(row, dict)
            and (timestamp := _date(row.get("date"))) is not None
            and (close := _number(row.get("close"))) is not None
        ]
        points.sort(key=lambda point: point.date)
        currency = item.get("currency") or data.get("currency")
        return points, currency

    def _fetch_yahoo_history(
        self,
        client: httpx.Client,
        symbol: str,
        period: MarketPeriod,
    ) -> tuple[list[MarketHistoryPoint], str | None]:
        response = client.get(
            f"{self.yahoo_base_url}/v8/finance/chart/{quote(symbol, safe='-._')}",
            params={"range": period, "interval": "1d", "includePrePost": "false"},
        )
        response.raise_for_status()
        payload = response.json().get("chart", {}).get("result", [])
        if not payload or not isinstance(payload[0], dict):
            return [], None
        result = payload[0]
        timestamps = result.get("timestamp", [])
        quote_data = (result.get("indicators", {}).get("quote", [{}]) or [{}])[0]
        rows: list[MarketHistoryPoint] = []
        for index, raw_timestamp in enumerate(timestamps):
            timestamp = _date(raw_timestamp)
            close = _number((quote_data.get("close") or [])[index] if index < len(quote_data.get("close") or []) else None)
            if timestamp is None or close is None:
                continue
            rows.append(
                MarketHistoryPoint(
                    date=timestamp,
                    open=_number((quote_data.get("open") or [])[index] if index < len(quote_data.get("open") or []) else None),
                    high=_number((quote_data.get("high") or [])[index] if index < len(quote_data.get("high") or []) else None),
                    low=_number((quote_data.get("low") or [])[index] if index < len(quote_data.get("low") or []) else None),
                    close=close,
                    volume=_number((quote_data.get("volume") or [])[index] if index < len(quote_data.get("volume") or []) else None),
                )
            )
        return rows, result.get("meta", {}).get("currency")

    def _search_global(self, query: str) -> list[MarketInstrument]:
        with self._client() as client:
            response = client.get(
                f"{self.yahoo_base_url}/v1/finance/search",
                params={"q": query.strip(), "quotesCount": 15, "newsCount": 0, "enableFuzzyQuery": "true"},
            )
            response.raise_for_status()
            payload = response.json()
            candidates = [
                item
                for item in payload.get("quotes", [])
                if isinstance(item, dict) and item.get("symbol")
            ][:10]
            if not candidates:
                return []

            symbols = ",".join(str(item["symbol"]) for item in candidates)
            quote_response = client.get(
                f"{self.yahoo_base_url}/v7/finance/quote",
                params={"symbols": symbols},
            )
            quote_items: dict[str, dict[str, Any]] = {}
            if quote_response.is_success:
                quote_payload = quote_response.json()
                quote_items = {
                    str(item.get("symbol", "")).upper(): item
                    for item in quote_payload.get("quoteResponse", {}).get("result", [])
                    if isinstance(item, dict) and item.get("symbol")
                }

            results: list[MarketInstrument] = []
            for item in candidates:
                symbol = str(item["symbol"]).upper()
                merged = {**item, **quote_items.get(symbol, {})}
                result = self._yahoo_item(merged)
                if result.price is None:
                    result = self._enrich_yahoo_chart(client, result)
                results.append(result)
            return results

    @staticmethod
    def _brapi_item(item: dict[str, Any]) -> MarketInstrument:
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        statistics = item.get("defaultKeyStatistics") if isinstance(item.get("defaultKeyStatistics"), dict) else {}
        if not statistics and isinstance(data.get("defaultKeyStatistics"), dict):
            statistics = data["defaultKeyStatistics"]
        symbol = item.get("symbol") or item.get("requestedSymbol") or data.get("symbol") or item.get("stock")
        return MarketInstrument(
            market="br",
            symbol=str(symbol or "").upper(),
            name=str(item.get("longName") or item.get("shortName") or item.get("name") or data.get("longName") or data.get("shortName") or symbol or "Ativo"),
            exchange="B3",
            asset_type=str(item.get("type") or item.get("subType") or "equity"),
            currency=item.get("currency") or data.get("currency") or "BRL",
            price=_number(item.get("regularMarketPrice") or item.get("price") or item.get("close") or data.get("regularMarketPrice")),
            change=_number(item.get("regularMarketChange") or item.get("change_abs") or data.get("regularMarketChange")),
            change_percent=_number(item.get("regularMarketChangePercent") or item.get("changePercent") or item.get("change") or data.get("regularMarketChangePercent")),
            market_cap=_number(item.get("marketCap") or item.get("market_cap") or data.get("marketCap")),
            volume=_number(item.get("regularMarketVolume") or item.get("volume") or data.get("regularMarketVolume")),
            previous_close=_number(item.get("regularMarketPreviousClose") or item.get("previousClose") or data.get("regularMarketPreviousClose")),
            average_volume=_number(item.get("averageDailyVolume3Month") or item.get("averageVolume") or data.get("averageDailyVolume3Month")),
            fifty_two_week_high=_number(item.get("fiftyTwoWeekHigh") or data.get("fiftyTwoWeekHigh")),
            fifty_two_week_low=_number(item.get("fiftyTwoWeekLow") or data.get("fiftyTwoWeekLow")),
            dividend_yield=_number(statistics.get("dividendYield") or item.get("dividendYield")),
            price_earnings=_number(item.get("priceEarnings") or statistics.get("trailingPE") or statistics.get("priceEarnings")),
            price_to_book=_number(statistics.get("priceToBook") or item.get("priceToBook")),
            return_on_equity=_number(statistics.get("returnOnEquity") or item.get("returnOnEquity")),
            shares_outstanding=_number(item.get("sharesOutstanding") or statistics.get("sharesOutstanding")),
            sector=item.get("sector") or data.get("sector"),
            subsector=item.get("subsector") or data.get("subsector"),
            logo_url=item.get("logourl") or item.get("logo") or data.get("logourl"),
            updated_at=_date(item.get("regularMarketTime") or data.get("regularMarketTime")),
            source="brapi",
        )

    @staticmethod
    def _merge_fii_details(item: MarketInstrument, fii: dict[str, Any]) -> MarketInstrument:
        return item.model_copy(
            update={
                "name": fii.get("name") or item.name,
                "price": _number(fii.get("price")) or item.price,
                "dividend_yield": _number(fii.get("dividendYield12m")) or item.dividend_yield,
                "dividend_yield_1m": _number(fii.get("dividendYield1m")),
                "price_to_book": _number(fii.get("priceToNav")) or item.price_to_book,
                "nav_per_share": _number(fii.get("navPerShare")),
                "shares_outstanding": _number(fii.get("sharesOutstanding")),
                "total_investors": _number(fii.get("totalInvestors")),
                "equity": _number(fii.get("equity")),
                "total_assets": _number(fii.get("totalAssets")),
                "segment": fii.get("segmentoAtuacao") or fii.get("segmentType"),
                "management_type": fii.get("tipoGestao"),
                "as_of_date": _date(fii.get("asOfDate")),
            }
        )

    def _load_fii_report(self, client: httpx.Client, symbol: str) -> FiiReportSummary | None:
        response = client.get(
            f"{self.brapi_base_url}/api/v2/fii/reports",
            params={"symbols": symbol, "limit": 1, "sortBy": "referenceDate", "sortOrder": "desc"},
        )
        if not response.is_success:
            return None
        payload = response.json()
        reports = [entry for entry in payload.get("reports", []) if isinstance(entry, dict)]
        if not reports:
            return None
        report = reports[0]
        return FiiReportSummary(
            reference_date=_date(report.get("referenceDate")),
            total_assets=_number(report.get("totalAssets")),
            equity=_number(report.get("equity")),
            nav_per_share=_number(report.get("navPerShare")),
            admin_fee_rate=_number(report.get("adminFeeRate")),
            monthly_return=_number(report.get("monthlyReturn")),
            monthly_patrimonial_return=_number(report.get("monthlyPatrimonialReturn")),
            monthly_dividend_yield=_number(report.get("monthlyDividendYield")),
            amortization_rate=_number(report.get("amortizationRate")),
            total_investors=_number(report.get("totalInvestors")),
            cash=_number(report.get("cash")),
            liquidity_needs=_number(report.get("liquidityNeeds")),
            government_bonds=_number(report.get("governmentBonds")),
            private_bonds=_number(report.get("privateBonds")),
            fixed_income_funds=_number(report.get("fixedIncomeFunds")),
            total_invested=_number(report.get("totalInvested")),
            real_estate_assets=_number(report.get("realEstateAssets")),
            cri=_number(report.get("cri")),
            lci=_number(report.get("lci")),
            fii_holdings=_number(report.get("fiiHoldings")),
            receivables=_number(report.get("receivables")),
            total_liabilities=_number(report.get("totalLiabilities")),
        )

    @staticmethod
    def _yahoo_item(item: dict[str, Any]) -> MarketInstrument:
        return MarketInstrument(
            market="global",
            symbol=str(item.get("symbol")),
            name=str(item.get("longname") or item.get("shortname") or item.get("symbol")),
            exchange=item.get("exchange") or item.get("exchDisp"),
            asset_type=item.get("quoteType"),
            currency=item.get("currency"),
            price=_number(item.get("regularMarketPrice")),
            change=_number(item.get("regularMarketChange")),
            change_percent=_number(item.get("regularMarketChangePercent")),
            previous_close=_number(item.get("regularMarketPreviousClose") or item.get("previousClose")),
            market_cap=_number(item.get("marketCap")),
            volume=_number(item.get("regularMarketVolume")),
            average_volume=_number(item.get("averageDailyVolume3Month") or item.get("averageVolume")),
            fifty_two_week_high=_number(item.get("fiftyTwoWeekHigh")),
            fifty_two_week_low=_number(item.get("fiftyTwoWeekLow")),
            dividend_yield=_number(item.get("dividendYield")),
            price_earnings=_number(item.get("trailingPE") or item.get("forwardPE")),
            price_to_book=_number(item.get("priceToBook")),
            return_on_equity=_number(item.get("returnOnEquity")),
            shares_outstanding=_number(item.get("sharesOutstanding")),
            sector=item.get("sector"),
            industry=item.get("industry"),
            updated_at=_date(item.get("regularMarketTime")),
            source="yahoo_finance",
        )

    def _enrich_yahoo_item(self, client: httpx.Client, item: dict[str, Any]) -> MarketInstrument:
        symbol = str(item.get("symbol", ""))
        response = client.get(
            f"{self.yahoo_base_url}/v7/finance/quote",
            params={"symbols": symbol},
        )
        if response.is_success:
            payload = response.json()
            results = payload.get("quoteResponse", {}).get("result", [])
            if results and isinstance(results[0], dict):
                return self._yahoo_item({**item, **results[0]})
        return self._enrich_yahoo_chart(client, self._yahoo_item(item))

    def _enrich_yahoo_chart(self, client: httpx.Client, item: MarketInstrument) -> MarketInstrument:
        if not item.symbol:
            return item
        response = client.get(
            f"{self.yahoo_base_url}/v8/finance/chart/{quote(item.symbol, safe='-._')}",
            params={"range": "5d", "interval": "1d", "includePrePost": "false"},
        )
        if not response.is_success:
            return item
        payload = response.json().get("chart", {}).get("result", [])
        if not payload or not isinstance(payload[0], dict):
            return item
        chart = payload[0]
        meta = chart.get("meta", {})
        timestamps = chart.get("timestamp", [])
        quote_data = (chart.get("indicators", {}).get("quote", [{}]) or [{}])[0]
        prices = [value for value in quote_data.get("close", []) if value is not None]
        volumes = [value for value in quote_data.get("volume", []) if value is not None]
        price = _number(meta.get("regularMarketPrice")) or (_number(prices[-1]) if prices else item.price)
        previous_close = _number(meta.get("previousClose") or meta.get("chartPreviousClose")) or item.previous_close
        change = item.change
        change_percent = item.change_percent
        if price is not None and previous_close:
            change = price - previous_close
            change_percent = (change / previous_close) * 100
        return item.model_copy(
            update={
                "currency": meta.get("currency") or item.currency,
                "price": price,
                "previous_close": previous_close,
                "change": change,
                "change_percent": change_percent,
                "volume": _number(volumes[-1]) if volumes else item.volume,
                "updated_at": _date(timestamps[-1]) if timestamps else item.updated_at,
            }
        )

    @staticmethod
    def _safe_error(error: Exception) -> str:
        message = str(error).strip()
        return message[:120] if message else "falha de comunicação"


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _with_returns(points: list[MarketHistoryPoint]) -> list[MarketHistoryPoint]:
    if not points or points[0].close == 0:
        return points
    base = points[0].close
    return [
        point.model_copy(update={"return_percent": round(((point.close / base) - 1) * 100, 6)})
        for point in points
    ]


def _history_summary(points: list[MarketHistoryPoint]) -> dict[str, Any]:
    if not points:
        return {"observation_count": 0, "average_volume": None, "annualized_volatility": None, "max_drawdown": None, "volatility_band": None}
    closes = [point.close for point in points]
    returns = [(closes[index] / closes[index - 1]) - 1 for index in range(1, len(closes)) if closes[index - 1]]
    average_volume = sum(point.volume for point in points if point.volume is not None) / max(sum(1 for point in points if point.volume is not None), 1)
    volatility = None
    if len(returns) > 1:
        mean = sum(returns) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
        volatility = round((variance ** 0.5) * (252 ** 0.5) * 100, 6)
    peak = closes[0]
    drawdowns: list[float] = []
    for close in closes:
        peak = max(peak, close)
        drawdowns.append((close / peak - 1) * 100 if peak else 0)
    max_drawdown = round(min(drawdowns), 6)
    band = None if volatility is None else "lower" if volatility < 15 else "intermediate" if volatility < 30 else "higher"
    return {
        "observation_count": len(points),
        "average_volume": round(average_volume, 2) if average_volume else None,
        "annualized_volatility": volatility,
        "max_drawdown": max_drawdown,
        "volatility_band": band,
    }
