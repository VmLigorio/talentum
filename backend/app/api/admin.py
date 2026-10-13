# Talentum — backend/app/api/admin.py
# Responsabilidade: Expõe endpoints HTTP, valida o usuário atual e orquestra as operações do domínio.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.security import hash_password
from app.db.database import get_db
from app.models import AuditLog, ClientPermission, ClientProfile, User, UserSession
from app.schemas.admin import AdminPasswordReset, AdminUserCreate, AdminUserStatusUpdate
from app.schemas.auth import UserResponse
from app.services.authorization import require_roles


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserResponse])
def list_users(
    role: str | None = None,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> list[User]:
    """Lista contas e, quando informado, filtra pelo papel validado."""
    query = select(User).order_by(User.name)
    if role is not None:
        if role not in {"admin", "advisor", "client"}:
            raise HTTPException(status_code=400, detail="Perfil de usuário inválido")
        query = query.where(User.role == role)
    return list(db.scalars(query).all())


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreate,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> User:
    """Cria uma conta e prepara perfil e permissões se for cliente."""
    # Pré-consulta melhora a mensagem sequencial; a unicidade do banco protege chamadas concorrentes.
    if db.scalar(select(User).where(User.email == payload.email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um usuário com este e-mail",
        )

    user = User(
        name=payload.name.strip(),
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    # Gera o identificador antes de criar os registros dependentes do cliente.
    db.flush()
    if payload.role == "client":
        db.add(ClientProfile(user_id=user.id))
        db.add(ClientPermission(client_id=user.id))

    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=user.id if payload.role == "client" else None,
            action="create",
            resource="user",
            resource_id=str(user.id),
        )
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: int,
    payload: AdminUserStatusUpdate,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> User:
    """Ativa ou desativa uma conta e encerra suas sessões ao desativá-la."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível desativar a própria conta",
        )
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    # O acesso muda na conta; ClientProfile.status não é sincronizado por esta rota.
    user.is_active = payload.is_active
    if not payload.is_active:
        # O incremento invalida tokens de acesso; a atualização abaixo revoga os refresh tokens.
        user.session_version += 1
        db.execute(
            update(UserSession)
            .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=user.id if user.role == "client" else None,
            action="update",
            resource="user_status",
            resource_id=str(user.id),
        )
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password", response_model=UserResponse)
def reset_user_password(
    user_id: int,
    payload: AdminPasswordReset,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> User:
    """Redefine a senha da conta e invalida todas as sessões existentes."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use a opção de alteração de senha da própria conta",
        )
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    user.password_hash = hash_password(payload.new_password)
    user.session_version += 1
    # Atualiza a versão e revoga refresh tokens na mesma transação da troca de senha.
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=user.id if user.role == "client" else None,
            action="change_password",
            resource="user",
            resource_id=str(user.id),
        )
    )
    db.commit()
    db.refresh(user)
    return user
