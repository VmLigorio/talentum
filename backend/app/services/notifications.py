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


DOCUMENT_REVIEW_KINDS = (
    ("income_proof", "Comprovante de renda"),
    ("address_proof", "Comprovante de endereço"),
)


def client_recipients(client_id: int, db: Session) -> list[int]:
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
    created = False
    for user_id in client_recipients(client_id, db):
        preferences = db.get(NotificationPreference, user_id)
        if preferences is None:
            preferences = NotificationPreference(user_id=user_id)
            db.add(preferences)
            db.flush()
        if not getattr(preferences, kind, True):
            continue
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
    return created


def sync_overdue_notifications(client_id: int, db: Session) -> bool:
    created = False
    today = date.today()
    alert_window_end = today + timedelta(days=3)
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
    """Creates one annual reminder for each required proof document."""
    changed = False
    today = date.today()
    expiration_date = today - timedelta(days=365)

    for kind, label in DOCUMENT_REVIEW_KINDS:
        latest = db.scalars(
            select(Document)
            .where(Document.client_id == client_id, Document.kind == kind)
            .order_by(Document.created_at.desc(), Document.id.desc())
        ).first()
        is_due = latest is None or latest.created_at.date() <= expiration_date

        if not is_due:
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
        changed = create_client_notification(
            db,
            client_id=client_id,
            kind="document_review_due",
            title=f"{label} precisa de atualização",
            message=message,
            dedupe_key=f"document-review-due:{kind}:{today.year}",
        ) or changed

    return changed
