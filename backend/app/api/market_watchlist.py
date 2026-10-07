# Talentum — backend/app/api/market_watchlist.py
# Responsabilidade: Expõe endpoints HTTP, valida o usuário atual e orquestra as operações do domínio.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models import AuditLog, MarketWatchlistItem, User
from app.schemas.market_watchlist import MarketWatchlistCreate, MarketWatchlistResponse
from app.services.authorization import require_client_manager
from app.services.market_data import MarketDataService


router = APIRouter(prefix="/market/watchlist", tags=["market-watchlist"])


def _find_client(client_id: int, db: Session) -> User:
    client = db.scalar(select(User).where(User.id == client_id, User.role == "client"))
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client


def _resolve_client_id(requested_client_id: int | None, current_user: User, db: Session) -> int:
    client_id = current_user.id if current_user.role == "client" else requested_client_id
    if client_id is None:
        raise HTTPException(status_code=400, detail="Informe o cliente da lista de acompanhamento")
    _find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    return client_id


def _response(item: MarketWatchlistItem, db: Session, service: MarketDataService) -> MarketWatchlistResponse:
    client = db.get(User, item.client_id)
    name = None
    price = None
    currency = None
    source = None
    try:
        instrument = service.details(item.symbol, item.market)
        name = instrument.name
        price = instrument.price
        currency = instrument.currency
        source = instrument.source
    except (httpx.HTTPError, ValueError):
        pass
    return MarketWatchlistResponse(
        id=item.id,
        client_id=item.client_id,
        client_name=client.name if client else "Cliente",
        created_by_user_id=item.created_by_user_id,
        symbol=item.symbol,
        market=item.market,
        note=item.note,
        name=name,
        current_price=price,
        currency=currency,
        source=source,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=list[MarketWatchlistResponse])
def list_market_watchlist(
    client_id: int | None = Query(default=None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MarketWatchlistResponse]:
    resolved_client_id = _resolve_client_id(client_id, current_user, db)
    items = db.scalars(
        select(MarketWatchlistItem)
        .where(MarketWatchlistItem.client_id == resolved_client_id)
        .order_by(MarketWatchlistItem.created_at.desc())
    ).all()
    service = MarketDataService()
    return [_response(item, db, service) for item in items]


@router.post("", response_model=MarketWatchlistResponse, status_code=status.HTTP_201_CREATED)
def create_market_watchlist_item(
    payload: MarketWatchlistCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MarketWatchlistResponse:
    client_id = _resolve_client_id(payload.client_id, current_user, db)
    item = MarketWatchlistItem(
        client_id=client_id,
        created_by_user_id=current_user.id,
        symbol=payload.symbol.strip().upper(),
        market=payload.market,
        note=payload.note.strip() if payload.note and payload.note.strip() else None,
    )
    db.add(item)
    try:
        db.flush()
        db.add(
            AuditLog(
                actor_user_id=current_user.id,
                client_user_id=client_id,
                action="create",
                resource="market_watchlist",
                resource_id=str(item.id),
                details={"symbol": item.symbol, "market": item.market},
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Este ativo já está na lista do cliente") from exc
    db.refresh(item)
    return _response(item, db, MarketDataService())


@router.delete("/{item_id}", response_model=MarketWatchlistResponse)
def remove_market_watchlist_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MarketWatchlistResponse:
    item = db.get(MarketWatchlistItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Ativo não encontrado na lista")
    require_client_manager(item.client_id, current_user, db)
    response = _response(item, db, MarketDataService())
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=item.client_id,
            action="delete",
            resource="market_watchlist",
            resource_id=str(item.id),
        )
    )
    db.delete(item)
    db.commit()
    return response
