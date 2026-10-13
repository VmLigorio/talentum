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
    """Busca uma conta de cliente ou retorna erro 404."""
    client = db.scalar(select(User).where(User.id == client_id, User.role == "client"))
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client


def _resolve_client_id(
    requested_client_id: int | None,
    current_user: User,
    db: Session,
) -> int:
    """Resolve o cliente da operação e valida a permissão de acesso."""
    client_id = current_user.id if current_user.role == "client" else requested_client_id
    if client_id is None:
        raise HTTPException(status_code=400, detail="Informe o cliente do alerta")
    _find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    return client_id


def _alert_response(alert: MarketAlert, db: Session) -> MarketAlertResponse:
    """Converte o alerta persistido no formato público da API."""
    # Inclui o nome do cliente para identificação do alerta no painel do Advisor.
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
    """Atualiza condições pendentes e lista os alertas do cliente."""
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
    """Cria um alerta de preço e registra a operação na auditoria."""
    # Resolve o cliente efetivo e valida a autorização antes de criar o alerta.
    client_id = _resolve_client_id(payload.client_id, current_user, db)
    # A validação de tamanho ocorre antes do strip; ticker só com espaços pode virar vazio (achado 67).
    # Converte o preço para Decimal antes da persistência.
    alert = MarketAlert(
        client_id=client_id,
        created_by_user_id=current_user.id,
        symbol=payload.symbol.strip().upper(),
        market=payload.market,
        target_price=Decimal(str(payload.target_price)),
        condition=payload.condition,
    )
    # Obtém o identificador gerado para vinculá-lo ao evento de auditoria.
    db.add(alert)
    db.flush()
    # Registra os parâmetros do alerta junto ao autor e ao cliente associado.
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="create",
            resource="market_alert",
            resource_id=str(alert.id),
        )
    )
    # Confirma alerta e auditoria na mesma transação e atualiza os dados gerados pelo banco.
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
    """Atualiza a condição ou o estado do alerta autorizado."""
    # Carrega o alerta pelo identificador e exige vínculo de gestão com seu cliente.
    alert = db.get(MarketAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    require_client_manager(alert.client_id, current_user, db)
    # Excluir campos ausentes preserva o valor atual; chaves enviadas com null continuam presentes.
    changes = payload.model_dump(exclude_unset=True)
    # Aplica apenas campos enviados; null explícito permanece sujeito às restrições do modelo.
    if "target_price" in changes:
        alert.target_price = Decimal(str(changes["target_price"]))
    if "condition" in changes:
        alert.condition = changes["condition"]
    # Este PATCH aceita triggered/cancelled sem executar os efeitos do monitoramento/cancelamento (achado 191).
    if "status" in changes:
        alert.status = changes["status"]
        if changes["status"] == "active":
            alert.triggered_at = None
    # Alterar o alvo/condição sem informar estado reabre o alerta e limpa o disparo anterior.
    if ("target_price" in changes or "condition" in changes) and "status" not in changes:
        alert.status = "active"
        alert.triggered_at = None
    # Mantém o conteúdo da alteração no histórico de auditoria antes de confirmar.
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=alert.client_id,
            action="update",
            resource="market_alert",
            resource_id=str(alert.id),
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
    """Cancela logicamente um alerta e registra a ação na auditoria."""
    alert = db.get(MarketAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    require_client_manager(alert.client_id, current_user, db)
    alert.status = "cancelled"  # Mantém o registro e sua trilha de auditoria, sem exclusão física.
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
