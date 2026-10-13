# Talentum — backend/app/api/actions.py
# Responsabilidade: Expõe endpoints HTTP, valida o usuário atual e orquestra as operações do domínio.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models import ActionItem, AuditLog, Goal, User
from app.schemas.action import ActionItemCreate, ActionItemResponse, ActionItemUpdate
from app.services.authorization import require_client_manager, require_roles


router = APIRouter(prefix="/clients", tags=["action-plan"])


def find_client(client_id: int, db: Session) -> User:
    """Localiza uma conta de cliente ou retorna erro 404."""
    client = db.scalar(select(User).where(User.id == client_id, User.role == "client"))
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client


def validate_goal(client_id: int, goal_id: int | None, db: Session) -> None:
    """Confirma que a meta opcional pertence ao mesmo cliente da ação."""
    if goal_id is None:
        return
    if db.scalar(select(Goal.id).where(Goal.id == goal_id, Goal.client_id == client_id)) is None:
        raise HTTPException(status_code=400, detail="A meta informada não pertence a este cliente")


def find_action(client_id: int, action_id: int, db: Session) -> ActionItem:
    """Busca uma ação dentro do cliente informado ou retorna erro 404."""
    action = db.scalar(
        select(ActionItem).where(ActionItem.id == action_id, ActionItem.client_id == client_id)
    )
    if action is None:
        raise HTTPException(status_code=404, detail="Ação não encontrada")
    return action


@router.get("/{client_id}/action-plan", response_model=list[ActionItemResponse])
def list_actions(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ActionItem]:
    """Lista ações do plano do cliente após validar acesso."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    # Define uma ordem estável na API; Advisor e Flutter aplicam ranking visual de prioridade.
    return list(
        db.scalars(
            select(ActionItem)
            .where(ActionItem.client_id == client_id)
            .order_by(ActionItem.status, ActionItem.due_date, ActionItem.priority, ActionItem.title)
        ).all()
    )


@router.post("/{client_id}/action-plan", response_model=ActionItemResponse, status_code=201)
def create_action(
    client_id: int,
    payload: ActionItemCreate,
    current_user: User = Depends(require_roles("admin", "advisor")),
    db: Session = Depends(get_db),
) -> ActionItem:
    """Cria uma ação vinculada a uma meta válida e registra auditoria."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    # Impede que uma ação do cliente aponte para a meta de outra pessoa.
    validate_goal(client_id, payload.goal_id, db)
    # O schema limita o tamanho, mas o título chega sem trim para a persistência.
    action = ActionItem(client_id=client_id, **payload.model_dump())
    db.add(action)
    # O flush gera o identificador necessário para registrar a auditoria antes do commit.
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="create",
            resource="action_item",
            resource_id=str(action.id),
        )
    )
    db.commit()
    db.refresh(action)
    return action


@router.patch("/{client_id}/action-plan/{action_id}", response_model=ActionItemResponse)
def update_action(
    client_id: int,
    action_id: int,
    payload: ActionItemUpdate,
    current_user: User = Depends(require_roles("admin", "advisor")),
    db: Session = Depends(get_db),
) -> ActionItem:
    """Atualiza os campos enviados da ação e registra a mudança."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    action = find_action(client_id, action_id, db)
    # Valida a meta somente quando informada; null pode remover o vínculo atual.
    validate_goal(client_id, payload.goal_id, db)
    # Campos omitidos ficam intactos; valores null enviados explicitamente seguem para o ORM.
    # O título, se enviado, também é aplicado sem normalização de espaços.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(action, field, value)
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="update",
            resource="action_item",
            resource_id=str(action.id),
        )
    )
    db.commit()
    db.refresh(action)
    return action


@router.delete("/{client_id}/action-plan/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_action(
    client_id: int,
    action_id: int,
    current_user: User = Depends(require_roles("admin", "advisor")),
    db: Session = Depends(get_db),
) -> None:
    """Remove uma ação após confirmar acesso e registrar a auditoria."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    action = find_action(client_id, action_id, db)
    # Auditoria e remoção são confirmadas juntas para não registrar ação inexistente.
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="delete",
            resource="action_item",
            resource_id=str(action.id),
        )
    )
    db.delete(action)
    db.commit()
