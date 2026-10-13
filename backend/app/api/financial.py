# Talentum — backend/app/api/financial.py
# Responsabilidade: Expõe endpoints HTTP, valida o usuário atual e orquestra as operações do domínio.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models import (
    AuditLog,
    ClientPermission,
    FinancialProfile,
    Goal,
    PatrimonyItem,
    User,
)
from app.schemas.financial import (
    FinancialProfileResponse,
    FinancialProfileUpdate,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    PatrimonyItemCreate,
    PatrimonyItemResponse,
    PatrimonyItemUpdate,
)
from app.services.authorization import require_client_manager, require_edit_permission


router = APIRouter(prefix="/clients", tags=["financial"])


def find_client(client_id: int, db: Session) -> User:
    """Busca uma conta de cliente ou encerra a requisição com 404."""
    client = db.scalar(
        select(User).where(User.id == client_id, User.role == "client")
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client


def record_audit(
    db: Session,
    *,
    actor_user_id: int,
    client_user_id: int,
    action: str,
    resource: str,
    resource_id: int | None = None,
) -> None:
    """Agenda um evento de auditoria dentro da transação atual."""
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            client_user_id=client_user_id,
            action=action,
            resource=resource,
            resource_id=str(resource_id) if resource_id is not None else None,
        )
    )


def check_read_access(client_id: int, current_user: User, db: Session) -> None:
    """Confirma que o cliente existe e que o usuário pode consultá-lo."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)


@router.get("/{client_id}/financial-profile", response_model=FinancialProfileResponse)
def get_financial_profile(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FinancialProfile:
    """Retorna o perfil financeiro do cliente autorizado."""
    check_read_access(client_id, current_user, db)
    profile = db.scalar(
        select(FinancialProfile).where(FinancialProfile.client_id == client_id)
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Perfil financeiro não cadastrado")
    return profile


@router.put("/{client_id}/financial-profile", response_model=FinancialProfileResponse)
def update_financial_profile(
    client_id: int,
    payload: FinancialProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FinancialProfile:
    """Cria ou atualiza renda, despesas e perfil de risco do cliente."""
    find_client(client_id, db)
    require_edit_permission(client_id, "can_edit_financial_profile", current_user, db)
    profile = db.scalar(
        select(FinancialProfile).where(FinancialProfile.client_id == client_id)
    )
    if profile is None:
        profile = FinancialProfile(client_id=client_id)
        db.add(profile)
    # PUT aplica o conjunto completo; campos ausentes recebem os padrões do schema.
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    # Esta edição não invalida avaliações de suitability já aprovadas; veja o achado 128.
    record_audit(
        db,
        actor_user_id=current_user.id,
        client_user_id=client_id,
        action="update",
        resource="financial_profile",
        resource_id=client_id,
    )
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{client_id}/patrimony", response_model=list[PatrimonyItemResponse])
def list_patrimony(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PatrimonyItem]:
    """Lista os itens patrimoniais do cliente em ordem de categoria."""
    check_read_access(client_id, current_user, db)
    return list(
        db.scalars(
            select(PatrimonyItem)
            .where(PatrimonyItem.client_id == client_id)
            .order_by(PatrimonyItem.category, PatrimonyItem.description)
        ).all()
    )


@router.post("/{client_id}/patrimony", response_model=PatrimonyItemResponse, status_code=201)
def create_patrimony_item(
    client_id: int,
    payload: PatrimonyItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatrimonyItem:
    """Registra um item patrimonial e audita a inclusão."""
    find_client(client_id, db)
    require_edit_permission(client_id, "can_edit_patrimony", current_user, db)
    # As restrições de tamanho do schema não removem espaços dos textos enviados diretamente à API.
    item = PatrimonyItem(client_id=client_id, **payload.model_dump())
    db.add(item)
    # Gera o ID antes de incluir a referência do item no registro de auditoria.
    db.flush()
    record_audit(
        db,
        actor_user_id=current_user.id,
        client_user_id=client_id,
        action="create",
        resource="patrimony_item",
        resource_id=item.id,
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{client_id}/patrimony/{item_id}", response_model=PatrimonyItemResponse)
def update_patrimony_item(
    client_id: int,
    item_id: int,
    payload: PatrimonyItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatrimonyItem:
    """Atualiza somente os campos enviados de um item do cliente."""
    find_client(client_id, db)
    require_edit_permission(client_id, "can_edit_patrimony", current_user, db)
    item = db.scalar(
        select(PatrimonyItem).where(
            PatrimonyItem.id == item_id, PatrimonyItem.client_id == client_id
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Item patrimonial não encontrado")
    # Campos omitidos ficam intactos; valores enviados, inclusive null e textos sem trim, seguem para o ORM.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    record_audit(
        db,
        actor_user_id=current_user.id,
        client_user_id=client_id,
        action="update",
        resource="patrimony_item",
        resource_id=item.id,
    )
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{client_id}/patrimony/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patrimony_item(
    client_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove um item patrimonial após validar acesso e registrar auditoria."""
    find_client(client_id, db)
    require_edit_permission(client_id, "can_edit_patrimony", current_user, db)
    item = db.scalar(
        select(PatrimonyItem).where(
            PatrimonyItem.id == item_id, PatrimonyItem.client_id == client_id
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Item patrimonial não encontrado")
    record_audit(
        db,
        actor_user_id=current_user.id,
        client_user_id=client_id,
        action="delete",
        resource="patrimony_item",
        resource_id=item.id,
    )
    db.delete(item)
    db.commit()


@router.get("/{client_id}/goals", response_model=list[GoalResponse])
def list_goals(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Goal]:
    """Lista as metas do cliente na ordem usada pelo acompanhamento."""
    check_read_access(client_id, current_user, db)
    return list(
        db.scalars(
            select(Goal)
            .where(Goal.client_id == client_id)
            .order_by(Goal.status, Goal.target_date, Goal.title)
        ).all()
    )


@router.post("/{client_id}/goals", response_model=GoalResponse, status_code=201)
def create_goal(
    client_id: int,
    payload: GoalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Goal:
    """Cria uma meta financeira e registra a ação na auditoria."""
    find_client(client_id, db)
    require_edit_permission(client_id, "can_edit_goals", current_user, db)
    # A validação de tamanho não normaliza o título; o texto é persistido como chegou no payload.
    goal = Goal(client_id=client_id, **payload.model_dump())
    db.add(goal)
    db.flush()
    record_audit(
        db,
        actor_user_id=current_user.id,
        client_user_id=client_id,
        action="create",
        resource="goal",
        resource_id=goal.id,
    )
    db.commit()
    db.refresh(goal)
    return goal


@router.patch("/{client_id}/goals/{goal_id}", response_model=GoalResponse)
def update_goal(
    client_id: int,
    goal_id: int,
    payload: GoalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Goal:
    """Atualiza os campos informados de uma meta existente do cliente."""
    find_client(client_id, db)
    require_edit_permission(client_id, "can_edit_goals", current_user, db)
    goal = db.scalar(
        select(Goal).where(Goal.id == goal_id, Goal.client_id == client_id)
    )
    if goal is None:
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    # Campos ausentes são preservados; null e textos enviados sem trim seguem para o ORM.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    record_audit(
        db,
        actor_user_id=current_user.id,
        client_user_id=client_id,
        action="update",
        resource="goal",
        resource_id=goal.id,
    )
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{client_id}/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    client_id: int,
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove uma meta após validar o vínculo e registrar auditoria."""
    find_client(client_id, db)
    require_edit_permission(client_id, "can_edit_goals", current_user, db)
    goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.client_id == client_id))
    if goal is None:
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    record_audit(
        db,
        actor_user_id=current_user.id,
        client_user_id=client_id,
        action="delete",
        resource="goal",
        resource_id=goal.id,
    )
    db.delete(goal)
    db.commit()
