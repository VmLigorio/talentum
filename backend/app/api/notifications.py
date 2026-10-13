# Talentum — backend/app/api/notifications.py
# Responsabilidade: Expõe endpoints HTTP, valida o usuário atual e orquestra as operações do domínio.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models import Notification, User
from app.schemas.notification import NotificationResponse
from app.services.notifications import (
    sync_document_review_notifications,
    sync_overdue_notifications,
)
from app.services.market_alerts import sync_market_alerts_for_user


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    unread_only: bool = Query(default=False),
    # A lista é limitada; a contagem total usa o endpoint /unread-count.
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Notification]:
    """Sincroniza avisos aplicáveis e retorna notificações recentes."""
    if current_user.role == "client":
        changed = sync_overdue_notifications(current_user.id, db)
        changed = sync_document_review_notifications(current_user.id, db) or changed
        if changed:
            db.commit()
    _, _, market_alerts_changed = sync_market_alerts_for_user(current_user, db)
    if market_alerts_changed:
        db.commit()
    # O escopo atual é o destinatário; não revalida o vínculo do Advisor com cada cliente notificado.
    query = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    return list(
        db.scalars(
            query.order_by(Notification.read_at.is_not(None), Notification.created_at.desc()).limit(limit)  # Não lidas primeiro; dentro de cada grupo, mais recentes antes.
        ).all()
    )


@router.get("/unread-count")
def unread_notification_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Conta notificações ainda não lidas pelo usuário autenticado."""
    # A contagem também considera todos os avisos do destinatário, inclusive vínculos já encerrados.
    count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.read_at.is_(None),
        )
    )
    return {"count": int(count or 0)}


@router.patch("/read-all", status_code=204)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Marca como lidas todas as notificações pendentes do usuário."""
    db.execute(  # O lote inclui avisos do destinatário ligados a vínculos já encerrados (achado 93).
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    db.commit()


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Notification:
    """Marca uma notificação própria como lida e devolve seu estado."""
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    notification.read_at = notification.read_at or datetime.now(timezone.utc)
    db.commit()
    db.refresh(notification)
    return notification
