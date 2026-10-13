# Talentum — backend/app/core/security.py
# Responsabilidade: Gera e valida hashes de senha, tokens JWT e hashes de sessões renováveis.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings


# Mantém explícito o algoritmo aceito ao assinar e validar os JWTs.
ALGORITHM = "HS256"
# Compartilha os parâmetros Argon2 usados para criar e conferir hashes de senha.
password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Gera um hash Argon2 adequado para armazenar uma senha."""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Compara a senha informada com o hash sem propagar erros de verificação."""
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def hash_refresh_token(token: str) -> str:
    """Produz o resumo SHA-256 usado para validar tokens renováveis salvos."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token(
    *,
    subject: int,
    token_type: str,
    expires_delta: timedelta,
    session_version: int | None = None,
    token_id: str | None = None,
) -> str:
    """Assina um token com prazo, finalidade e identificador de sessão."""
    now = datetime.now(timezone.utc)
    # Claims comuns distinguem sujeito, finalidade, validade e identificador;
    # a versão da sessão é opcional para manter o helper reutilizável.
    payload: dict[str, object] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": token_id or str(uuid4()),
    }
    if session_version is not None:
        payload["sv"] = session_version
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: str) -> dict[str, object]:
    """Valida assinatura e finalidade e retorna os dados do token."""
    # Exige o conjunto mínimo de claims e limita o algoritmo aceito à constante local.
    payload = jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=[ALGORITHM],
        options={"require": ["sub", "type", "iat", "exp", "jti"]},
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("unexpected token type")
    return payload
