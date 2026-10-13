# Talentum — backend/app/api/dependencies.py
# Responsabilidade: Define dependências HTTP para autenticar e carregar o usuário da requisição.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.database import get_db
from app.models import User


# Permite que get_current_user normalize a ausência de credenciais na resposta da API.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Valida o token Bearer e carrega a conta ativa da requisição."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # Não revela se faltou token, se ele expirou ou se a conta foi desativada.
    if credentials is None:
        raise credentials_error
    token = credentials.credentials
    try:
        payload = decode_token(token, "access")
        user_id = int(payload["sub"])
    except (ValueError, KeyError, TypeError, jwt.InvalidTokenError) as exc:
        raise credentials_error from exc

    # O token identifica a conta, mas o estado atual do banco decide se ela segue ativa.
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise credentials_error

    # Incrementar session_version invalida todos os access tokens emitidos antes.
    if payload.get("sv") != user.session_version:
        raise credentials_error

    return user
