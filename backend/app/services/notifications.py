# Talentum — backend/app/services/notifications.py
# Responsabilidade: Concentra regras de negócio e integrações reutilizáveis, mantendo as rotas mais simples.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ActionItem,
    ClientProfile,
    Document,
    Goal,
    Notification,
    NotificationPreference,
    User,
)


# Tipos de comprovante sujeitos à revisão anual e seus nomes nas mensagens.
DOCUMENT_REVIEW_KINDS = (
    ("income_proof", "Comprovante de renda"),
    ("address_proof", "Comprovante de endereço"),
)


def client_recipients(client_id: int, db: Session) -> list[int]:
    """Retorna o cliente e, quando vinculado, seu assessor como destinatários."""
    recipients = [client_id]
    advisor_id = db.scalar(
        select(ClientProfile.advisor_id).where(ClientProfile.user_id == client_id)
    )
    if advisor_id is not None:
        recipients.append(advisor_id)
    return recipients


def create_client_notification(
    db: Session,
    *,
    client_id: int,
    kind: str,
    title: str,
    message: str,
    dedupe_key: str,
) -> bool:
    """Cria avisos habilitados para cliente e assessor sem duplicar eventos."""
    created = False
    for user_id in client_recipients(client_id, db):
        # As preferências são individuais: desativar o aviso de um destinatário não afeta o outro.
        preferences = db.get(NotificationPreference, user_id)
        if preferences is None:
            preferences = NotificationPreference(user_id=user_id)
            db.add(preferences)
            db.flush()
        if not getattr(preferences, kind, True):
            continue
        # A consulta evita repetição sequencial; consulta e inserção separadas ainda disputam concorrência (achado 53).
        existing = db.scalar(
            select(Notification.id).where(
                Notification.user_id == user_id,
                Notification.dedupe_key == dedupe_key,
            )
        )
        if existing is not None:
            continue
        db.add(
            Notification(
                user_id=user_id,
                client_id=client_id,
                kind=kind,
                title=title,
                message=message,
                dedupe_key=dedupe_key,
            )
        )
        created = True
    # O retorno informa se houve ao menos uma inserção pendente nesta transação; o chamador confirma o commit.
    return created


def sync_overdue_notifications(client_id: int, db: Session) -> bool:
    """Gera avisos idempotentes para metas e ações vencidas ou próximas."""
    created = False
    today = date.today()
    # Lembretes de prazo são emitidos para vencimentos nos próximos três dias corridos.
    alert_window_end = today + timedelta(days=3)
    # Separa ações não concluídas cujo prazo já passou para produzir avisos de atraso.
    overdue_actions = db.scalars(
        select(ActionItem).where(
            ActionItem.client_id == client_id,
            ActionItem.status != "completed",
            ActionItem.due_date.is_not(None),
            ActionItem.due_date < today,
        )
    ).all()
    for action in overdue_actions:
        created = create_client_notification(
            db,
            client_id=client_id,
            kind="action_overdue",
            title="Ação atrasada",
            message=f'A ação "{action.title}" está atrasada.',
            dedupe_key=f"action-overdue:{action.id}:{action.due_date.isoformat()}",
        ) or created

    # Busca ações não concluídas que vencem entre hoje e o fim da janela de lembrete.
    upcoming_actions = db.scalars(
        select(ActionItem).where(
            ActionItem.client_id == client_id,
            ActionItem.status != "completed",
            ActionItem.due_date >= today,
            ActionItem.due_date <= alert_window_end,
        )
    ).all()
    for action in upcoming_actions:
        created = create_client_notification(
            db,
            client_id=client_id,
            kind="action_due_soon",
            title="Ação próxima do prazo",
            message=f'A ação "{action.title}" vence em {action.due_date.strftime("%d/%m/%Y")}.',
            dedupe_key=f"action-due-soon:{action.id}:{action.due_date.isoformat()}",
        ) or created

    # Aplica o mesmo critério de atraso às metas que ainda não foram concluídas.
    overdue_goals = db.scalars(
        select(Goal).where(
            Goal.client_id == client_id,
            Goal.status != "completed",
            Goal.target_date.is_not(None),
            Goal.target_date < today,
        )
    ).all()
    for goal in overdue_goals:
        created = create_client_notification(
            db,
            client_id=client_id,
            kind="goal_overdue",
            title="Meta vencida",
            message=f'A meta "{goal.title}" passou do prazo.',
            dedupe_key=f"goal-overdue:{goal.id}:{goal.target_date.isoformat()}",
        ) or created

    # Localiza metas não concluídas próximas do prazo para emitir aviso antecipado.
    upcoming_goals = db.scalars(
        select(Goal).where(
            Goal.client_id == client_id,
            Goal.status != "completed",
            Goal.target_date >= today,
            Goal.target_date <= alert_window_end,
        )
    ).all()
    for goal in upcoming_goals:
        created = create_client_notification(
            db,
            client_id=client_id,
            kind="goal_due_soon",
            title="Meta próxima do prazo",
            message=f'A meta "{goal.title}" vence em {goal.target_date.strftime("%d/%m/%Y")}.',
            dedupe_key=f"goal-due-soon:{goal.id}:{goal.target_date.isoformat()}",
        ) or created
    return created


def sync_document_review_notifications(client_id: int, db: Session) -> bool:
    """Cria um lembrete anual para cada comprovante que precisa ser renovado."""
    changed = False
    today = date.today()
    # Considera vencido o comprovante que completou pelo menos 365 dias.
    expiration_date = today - timedelta(days=365)

    # Analisa cada tipo de comprovante que exige renovação anual.
    for kind, label in DOCUMENT_REVIEW_KINDS:
        # Usa o documento mais recente do tipo para decidir se a revisão está em dia.
        latest = db.scalars(
            select(Document)
            .where(Document.client_id == client_id, Document.kind == kind)
            .order_by(Document.created_at.desc(), Document.id.desc())
        ).first()
        is_due = latest is None or latest.created_at.date() <= expiration_date

        if not is_due:
            # A chegada de um documento recente encerra lembretes antigos ainda não lidos.
            # O filtro usa client_id, então alcança todos os destinatários, inclusive o Advisor.
            unread_due_notifications = db.scalars(
                select(Notification).where(
                    Notification.client_id == client_id,
                    Notification.kind == "document_review_due",
                    Notification.read_at.is_(None),
                    Notification.message.contains(label),
                )
            ).all()
            for notification in unread_due_notifications:
                notification.read_at = datetime.now(timezone.utc)
                changed = True
            continue

        # Explica se falta um comprovante ou se o último envio ultrapassou o prazo.
        if latest is None:
            message = (
                f"Não há {label.lower()} cadastrado. "
                "Solicite ao seu Advisor o envio do documento."
            )
        else:
            message = (
                f"{label} enviado em {latest.created_at:%d/%m/%Y} "
                "precisa ser atualizado anualmente. Solicite ao seu Advisor "
                "o envio de uma versão atualizada."
            )
        # A chave anual evita recriar o mesmo lembrete em toda sincronização.
        changed = create_client_notification(
            db,
            client_id=client_id,
            kind="document_review_due",
            title=f"{label} precisa de atualização",
            message=message,
            dedupe_key=f"document-review-due:{kind}:{today.year}",
        ) or changed

    return changed
