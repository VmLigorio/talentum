# Talentum — backend/app/services/authorization.py
# Responsabilidade: Concentra regras de negócio e integrações reutilizáveis, mantendo as rotas mais simples.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models import ClientPermission, ClientProfile, User


def require_roles(*allowed_roles: str) -> Callable:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para esta operação",
            )
        return current_user

    return dependency


def can_manage_client(
    client_id: int,
    current_user: User,
    db: Session,
) -> bool:
    if current_user.role == "admin":
        return True
    if current_user.role == "advisor":
        return db.scalar(
            select(ClientProfile.id).where(
                ClientProfile.user_id == client_id,
                ClientProfile.advisor_id == current_user.id,
            )
        ) is not None
    return current_user.role == "client" and current_user.id == client_id


def require_client_manager(
    client_id: int,
    current_user: User,
    db: Session,
) -> None:
    if not can_manage_client(client_id, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem acesso a este cliente",
        )


def require_edit_permission(
    client_id: int,
    permission_field: str,
    current_user: User,
    db: Session,
) -> None:
    if current_user.role in {"admin", "advisor"}:
        require_client_manager(client_id, current_user, db)
        return

    if current_user.role != "client" or current_user.id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para esta operação",
        )

    # O próprio cliente pode completar o cadastro e enviar seus comprovantes.
    # Alterações financeiras e patrimoniais continuam dependendo da permissão do Advisor.
    if permission_field in {"can_edit_profile", "can_upload_documents"}:
        return

    permissions = db.scalar(
        select(ClientPermission).where(ClientPermission.client_id == client_id)
    )
    if permissions is None or not getattr(permissions, permission_field, False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta operação não está habilitada para o seu perfil",
        )
