# Talentum — backend/app/api/clients.py
# Responsabilidade: Expõe endpoints HTTP, valida o usuário atual e orquestra as operações do domínio.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models import AuditLog, ClientPermission, ClientProfile, User
from app.schemas.client import (
    ClientDetailResponse,
    ClientAssignmentResponse,
    ClientAssignmentUpdate,
    AdvisorSummary,
    AuditLogResponse,
    ClientProfileDataResponse,
    ClientProfileUpdate,
    ClientPermissionResponse,
    ClientPermissionUpdate,
    ClientSummary,
)
from app.services.authorization import (
    can_manage_client,
    require_client_manager,
    require_roles,
)


router = APIRouter(prefix="/clients", tags=["clients"])


def permission_response(
    client_id: int, permissions: ClientPermission | None
) -> ClientPermissionResponse:
    """Monta permissões padrão negadas quando ainda não há registro."""
    if permissions is None:
        return ClientPermissionResponse(
            client_id=client_id,
            can_edit_profile=False,
            can_edit_financial_profile=False,
            can_edit_patrimony=False,
            can_edit_goals=False,
            can_upload_documents=False,
        )
    return ClientPermissionResponse.model_validate(permissions)


def find_client(client_id: int, db: Session) -> User:
    """Localiza uma conta com papel de cliente ou retorna erro 404."""
    # O status usado depois da checagem de vínculo também oculta a existência do identificador.
    client = db.scalar(
        select(User).where(User.id == client_id, User.role == "client")
    )
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente não encontrado",
        )
    return client


@router.get("", response_model=list[ClientSummary])
def list_clients(
    current_user: User = Depends(require_roles("admin", "advisor")),
    db: Session = Depends(get_db),
) -> list[User]:
    """Lista clientes e restringe assessores aos clientes atribuídos."""
    query = select(User).where(User.role == "client").order_by(User.name)
    if current_user.role == "advisor":
        assigned_ids = select(ClientProfile.user_id).where(
            ClientProfile.advisor_id == current_user.id
        )
        query = query.where(User.id.in_(assigned_ids))
    return list(db.scalars(query).all())


@router.get("/me/permissions", response_model=ClientPermissionResponse)
def my_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClientPermissionResponse:
    """Retorna as permissões de edição da própria conta do cliente."""
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente clientes possuem permissões de edição",
        )
    permissions = db.scalar(
        select(ClientPermission).where(ClientPermission.client_id == current_user.id)
    )
    return permission_response(current_user.id, permissions)


def profile_response(
    client: User, profile: ClientProfile | None, db: Session
) -> ClientProfileDataResponse:
    """Combina dados da conta, perfil cadastral e nome do assessor."""
    # O vínculo e o cadastro são opcionais, então a resposta precisa funcionar
    # também antes de o cliente completar o perfil ou receber um assessor.
    advisor = (
        db.scalar(select(User).where(User.id == profile.advisor_id, User.role == "advisor"))
        if profile and profile.advisor_id
        else None
    )
    # Identidade vem da conta; os demais dados vêm do perfil quando disponível.
    return ClientProfileDataResponse(
        client_id=client.id,
        name=client.name,
        email=client.email,
        phone=profile.phone if profile else None,
        father_name=profile.father_name if profile else None,
        mother_name=profile.mother_name if profile else None,
        address_street=profile.address_street if profile else None,
        address_number=profile.address_number if profile else None,
        address_city=profile.address_city if profile else None,
        address_zip_code=profile.address_zip_code if profile else None,
        address_state=profile.address_state if profile else None,
        # Status do perfil cadastral é independente da ativação da conta em User.is_active.
        status=profile.status if profile else "active",
        advisor_id=profile.advisor_id if profile else None,
        advisor_name=advisor.name if advisor else None,
    )


@router.get("/advisors", response_model=list[AdvisorSummary])
def list_advisors(
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> list[User]:
    """Lista assessores ativos para uso administrativo."""
    return list(
        db.scalars(
            select(User)
            .where(User.role == "advisor", User.is_active.is_(True))
            .order_by(User.name)
        ).all()
    )


@router.get("/{client_id}/profile", response_model=ClientProfileDataResponse)
def get_profile(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClientProfileDataResponse:
    """Retorna o perfil cadastral de um cliente que o usuário pode gerenciar."""
    client = find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    profile = db.scalar(select(ClientProfile).where(ClientProfile.user_id == client_id))
    return profile_response(client, profile, db)


@router.put("/{client_id}/profile", response_model=ClientProfileDataResponse)
def update_profile(
    client_id: int,
    payload: ClientProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClientProfileDataResponse:
    """Atualiza os dados cadastrais e registra as alterações na auditoria."""
    client = find_client(client_id, db)
    # A rota exige Advisor/admin; a flag can_edit_profile não habilita acesso do cliente aqui.
    if current_user.role not in {"admin", "advisor"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente o Advisor ou o administrador podem atualizar os dados cadastrais",
        )
    require_client_manager(client_id, current_user, db)
    profile = db.scalar(select(ClientProfile).where(ClientProfile.user_id == client_id))
    if profile is None:
        # A primeira atualização cadastral cria o registro complementar do cliente.
        profile = ClientProfile(user_id=client_id)
        db.add(profile)
    if payload.name is not None:
        # O schema mede o texto antes desta remoção; uma entrada só com espaços pode se tornar vazia aqui.
        client.name = payload.name.strip()
    for field in (
        "phone",
        "father_name",
        "mother_name",
        "address_street",
        "address_number",
        "address_city",
        "address_zip_code",
        "address_state",
    ):
        if field in payload.model_fields_set:
            value = getattr(payload, field)
            setattr(profile, field, value.strip() if value else None)
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="update",
            resource="client_profile",
            resource_id=str(client_id),
        )
    )
    db.commit()
    db.refresh(profile)
    return profile_response(client, profile, db)


@router.put("/{client_id}/assignment", response_model=ClientAssignmentResponse)
def update_assignment(
    client_id: int,
    payload: ClientAssignmentUpdate,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> ClientAssignmentResponse:
    """Atribui ou remove o assessor responsável por um cliente."""
    # Confirma que o cliente existe antes de alterar seu responsável.
    client = find_client(client_id, db)
    advisor = None
    # Quando informado, o destino precisa ser uma conta ativa com papel de Advisor.
    if payload.advisor_id is not None:
        advisor = db.scalar(
            select(User).where(
                User.id == payload.advisor_id,
                User.role == "advisor",
                User.is_active.is_(True),
            )
        )
        if advisor is None:
            raise HTTPException(status_code=404, detail="Advisor não encontrado")

    # Cria o perfil mínimo se necessário; advisor_id nulo representa a remoção do vínculo.
    profile = db.scalar(select(ClientProfile).where(ClientProfile.user_id == client_id))
    if profile is None:
        profile = ClientProfile(user_id=client_id)
        db.add(profile)
    profile.advisor_id = payload.advisor_id
    # Registra quem fez a atribuição e qual vínculo foi solicitado antes do commit.
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="assign",
            resource="client_advisor",
            resource_id=str(client_id),
        )
    )
    db.commit()
    # Devolve os identificadores persistidos e o nome resolvido para a interface.
    return ClientAssignmentResponse(
        client_id=client.id,
        advisor_id=profile.advisor_id,
        advisor_name=advisor.name if advisor else None,
    )


@router.get("/{client_id}/audit-log", response_model=list[AuditLogResponse])
def list_audit_log(
    client_id: int,
    current_user: User = Depends(require_roles("admin", "advisor")),
    db: Session = Depends(get_db),
) -> list[AuditLogResponse]:
    """Retorna metadados mínimos de até 50 eventos recentes de auditoria."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    rows = db.execute(
        select(
            AuditLog.id,
            AuditLog.actor_user_id,
            User.name,
            AuditLog.action,
            AuditLog.resource,
            AuditLog.resource_id,
            AuditLog.created_at,
        )
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.client_user_id == client_id)
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    ).all()
    return [
        AuditLogResponse(
            id=log_id,
            actor_user_id=actor_user_id,
            actor_name=actor_name,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=None,
            created_at=created_at,
        )
        for log_id, actor_user_id, actor_name, action, resource, resource_id, created_at in rows
    ]


@router.get("/{client_id}", response_model=ClientDetailResponse)
def get_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClientDetailResponse:
    """Reúne conta, perfil cadastral e permissões em uma única resposta."""
    client = find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    profile = db.scalar(
        select(ClientProfile).where(ClientProfile.user_id == client_id)
    )
    permissions = db.scalar(
        select(ClientPermission).where(ClientPermission.client_id == client_id)
    )
    return ClientDetailResponse(
        **ClientSummary.model_validate(client).model_dump(),
        profile=profile,
        permissions=permission_response(client_id, permissions),
    )


@router.get("/{client_id}/permissions", response_model=ClientPermissionResponse)
def get_permissions(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClientPermissionResponse:
    """Consulta as permissões de edição de um cliente autorizado."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    permissions = db.scalar(
        select(ClientPermission).where(ClientPermission.client_id == client_id)
    )
    return permission_response(client_id, permissions)


@router.put("/{client_id}/permissions", response_model=ClientPermissionResponse)
def update_permissions(
    client_id: int,
    payload: ClientPermissionUpdate,
    current_user: User = Depends(require_roles("admin", "advisor")),
    db: Session = Depends(get_db),
) -> ClientPermissionResponse:
    """Atualiza as permissões de edição e registra a mudança."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    permissions = db.scalar(
        select(ClientPermission).where(ClientPermission.client_id == client_id)
    )
    if permissions is None:
        permissions = ClientPermission(client_id=client_id)
        db.add(permissions)

    # Aplica somente os campos enviados para permitir atualizar as permissões parcialmente.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(permissions, field, value)

    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="update",
            resource="client_permissions",
            resource_id=str(client_id),
        )
    )
    db.commit()
    db.refresh(permissions)
    return permission_response(client_id, permissions)
