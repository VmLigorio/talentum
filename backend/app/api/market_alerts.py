# Talentum — backend/app/api/market_alerts.py
# Responsabilidade: Expõe endpoints HTTP, valida o usuário atual e orquestra as operações do domínio.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models import AuditLog, ClientProfile, MarketAlert, User
from app.schemas.market_alert import MarketAlertCreate, MarketAlertResponse, MarketAlertUpdate
from app.services.authorization import require_client_manager
from app.services.market_alerts import sync_market_alerts_for_client


router = APIRouter(prefix="/market/alerts", tags=["market-alerts"])


def _find_client(client_id: int, db: Session) -> User:
    client = db.scalar(select(User).where(User.id == client_id, User.role == "client"))
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client


def _resolve_client_id(
    requested_client_id: int | None,
    current_user: User,
    db: Session,
) -> int:
    client_id = current_user.id if current_user.role == "client" else requested_client_id
    if client_id is None:
        raise HTTPException(status_code=400, detail="Informe o cliente do alerta")
    _find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    return client_id


def _alert_response(alert: MarketAlert, db: Session) -> MarketAlertResponse:
    client = db.get(User, alert.client_id)
    return MarketAlertResponse(
        id=alert.id,
        client_id=alert.client_id,
        client_name=client.name if client else "Cliente",
        created_by_user_id=alert.created_by_user_id,
        symbol=alert.symbol,
        market=alert.market,
        target_price=float(alert.target_price),
        condition=alert.condition,
        status=alert.status,
        last_price=float(alert.last_price) if alert.last_price is not None else None,
        triggered_at=alert.triggered_at,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


@router.get("", response_model=list[MarketAlertResponse])
def list_market_alerts(
    client_id: int | None = Query(default=None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MarketAlertResponse]:
    resolved_client_id = _resolve_client_id(client_id, current_user, db)
    _, _, changed = sync_market_alerts_for_client(resolved_client_id, db)
    if changed:
        db.commit()
    alerts = db.scalars(
        select(MarketAlert)
        .where(MarketAlert.client_id == resolved_client_id)
        .order_by(MarketAlert.status, MarketAlert.created_at.desc())
    ).all()
    return [_alert_response(alert, db) for alert in alerts]


@router.post("", response_model=MarketAlertResponse, status_code=status.HTTP_201_CREATED)
def create_market_alert(
    payload: MarketAlertCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MarketAlertResponse:
    client_id = _resolve_client_id(payload.client_id, current_user, db)
    alert = MarketAlert(
        client_id=client_id,
        created_by_user_id=current_user.id,
        symbol=payload.symbol.strip().upper(),
        market=payload.market,
        target_price=Decimal(str(payload.target_price)),
        condition=payload.condition,
    )
    db.add(alert)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="create",
            resource="market_alert",
            resource_id=str(alert.id),
            details={
                "symbol": alert.symbol,
                "market": alert.market,
                "target_price": str(alert.target_price),
                "condition": alert.condition,
            },
        )
    )
    db.commit()
    db.refresh(alert)
    return _alert_response(alert, db)


@router.patch("/{alert_id}", response_model=MarketAlertResponse)
def update_market_alert(
    alert_id: int,
    payload: MarketAlertUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MarketAlertResponse:
    alert = db.get(MarketAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    require_client_manager(alert.client_id, current_user, db)
    changes = payload.model_dump(exclude_unset=True)
    if "target_price" in changes:
        alert.target_price = Decimal(str(changes["target_price"]))
    if "condition" in changes:
        alert.condition = changes["condition"]
    if "status" in changes:
        alert.status = changes["status"]
        if changes["status"] == "active":
            alert.triggered_at = None
    if ("target_price" in changes or "condition" in changes) and "status" not in changes:
        alert.status = "active"
        alert.triggered_at = None
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=alert.client_id,
            action="update",
            resource="market_alert",
            resource_id=str(alert.id),
            details=changes,
        )
    )
    db.commit()
    db.refresh(alert)
    return _alert_response(alert, db)


@router.delete("/{alert_id}", response_model=MarketAlertResponse)
def cancel_market_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MarketAlertResponse:
    alert = db.get(MarketAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    require_client_manager(alert.client_id, current_user, db)
    alert.status = "cancelled"
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=alert.client_id,
            action="cancel",
            resource="market_alert",
            resource_id=str(alert.id),
        )
    )
    db.commit()
    db.refresh(alert)
    return _alert_response(alert, db)
