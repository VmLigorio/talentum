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
            details={"role": payload.role},
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
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível desativar a própria conta",
        )
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    user.is_active = payload.is_active
    if not payload.is_active:
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
            details={"is_active": payload.is_active},
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
            details={"reset_by_admin": True},
        )
    )
    db.commit()
    db.refresh(user)
    return user
