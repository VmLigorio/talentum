# Talentum — backend/app/api/market.py
# Responsabilidade: Expõe endpoints HTTP, valida o usuário atual e orquestra as operações do domínio.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException

from app.models import User
from app.schemas.market import MarketHistoryResponse, MarketInstrument, MarketPeriod, MarketRegion, MarketSearchResponse
from app.services.authorization import require_roles
from app.services.market_data import MarketDataService


router = APIRouter(prefix="/market", tags=["market"])


@router.get("/search", response_model=MarketSearchResponse)
def search_market(
    q: str = Query(min_length=1, max_length=64),
    market: MarketRegion = Query(default="all"),
    current_user: User = Depends(require_roles("admin", "advisor")),
) -> MarketSearchResponse:
    """Pesquisa ativos nas fontes disponíveis para assessores e administradores."""
    # A dependência valida o papel; o objeto do usuário não é necessário na consulta externa.
    del current_user
    # O tamanho mínimo foi validado antes do strip; espaços podem deixar query vazia (achado 144).
    query = q.strip()
    results, warnings = MarketDataService().search(query, market)
    return MarketSearchResponse(
        query=query,
        market=market,
        fetched_at=datetime.now(timezone.utc),
        results=results,
        warnings=warnings,
    )


@router.get("/details", response_model=MarketInstrument)
def market_details(
    symbol: str = Query(min_length=1, max_length=32),
    market: MarketRegion = Query(),
    current_user: User = Depends(require_roles("admin", "advisor")),
) -> MarketInstrument:
    """Consulta dados atuais de um ativo e traduz falhas externas em HTTP."""
    # Mantém a autenticação por papel mesmo sem usar outros dados do usuário no provedor.
    del current_user
    try:
        return MarketDataService().details(symbol, market)
    except ValueError as exc:
        # O mesmo tipo também pode vir de JSON inválido do provedor e virar falso 404.
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        # Erros de transporte ou protocolo do provedor são falhas de gateway, não do cliente.
        raise HTTPException(status_code=502, detail="A fonte de dados não respondeu ao detalhamento.") from exc


@router.get("/history", response_model=MarketHistoryResponse)
def market_history(
    symbol: str = Query(min_length=1, max_length=32),
    market: MarketRegion = Query(),
    period: MarketPeriod = Query(default="1y"),
    current_user: User = Depends(require_roles("admin", "advisor")),
) -> MarketHistoryResponse:
    """Retorna o histórico do ativo no período solicitado."""
    # A dependência restringe a consulta a assessores e administradores.
    del current_user
    try:
        return MarketDataService().history(symbol, market, period)
    except ValueError as exc:
        # Distinguir ativo inexistente de payload inválido exige erro próprio do adaptador.
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        # Mantém separado o erro da fonte externa de um símbolo/período inválido.
        raise HTTPException(status_code=502, detail="A fonte de dados não respondeu ao histórico.") from exc
