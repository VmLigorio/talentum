from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.security import (
    create_token,
    decode_token,
    hash_refresh_token,
    verify_password,
)
from app.core.rate_limit import LoginRateLimiter
from app.db.database import get_db
from app.models import User, UserSession
from app.models import AuditLog
from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)


router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
login_rate_limiter = LoginRateLimiter(
    settings.login_rate_limit_attempts,
    settings.login_rate_limit_window_seconds,
    settings.redis_url,
    settings.redis_required,
)
invalid_credentials = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="E-mail ou senha inválidos",
    headers={"WWW-Authenticate": "Bearer"},
)


def issue_tokens(db: Session, user: User) -> TokenResponse:
    settings = get_settings()
    access_ttl = timedelta(minutes=settings.access_token_expire_minutes)
    refresh_ttl = timedelta(days=settings.refresh_token_expire_days)
    session_id = str(uuid4())
    refresh_token = create_token(
        subject=user.id,
        token_type="refresh",  # nosec B106
        expires_delta=refresh_ttl,
        token_id=session_id,
    )
    expires_at = datetime.now(timezone.utc) + refresh_ttl
    db.add(
        UserSession(
            id=session_id,
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(refresh_token),
            expires_at=expires_at,
        )
    )
    access_token = create_token(
        subject=user.id,
        token_type="access",  # nosec B106
        expires_delta=access_ttl,
        session_version=user.session_version,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=int(access_ttl.total_seconds()),
    )


@router.post("/login", response_model=TokenResponse)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    client_host = request.client.host if request.client else "unknown"
    rate_limit_key = f"{client_host}:{payload.email}"
    try:
        allowed = login_rate_limiter.allow(rate_limit_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Proteção de login temporariamente indisponível") from exc
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login. Tente novamente mais tarde.",
            headers={"Retry-After": str(settings.login_rate_limit_window_seconds)},
        )
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active or not verify_password(
        payload.password, user.password_hash
    ):
        try:
            login_rate_limiter.register_failure(rate_limit_key)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail="Proteção de login temporariamente indisponível") from exc
        raise invalid_credentials

    try:
        login_rate_limiter.reset(rate_limit_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Proteção de login temporariamente indisponível") from exc
    tokens = issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        token_payload = decode_token(payload.refresh_token, "refresh")
        session_id = str(token_payload["jti"])
        user_id = int(token_payload["sub"])
    except (ValueError, KeyError, TypeError, jwt.InvalidTokenError) as exc:
        raise invalid_credentials from exc

    user_session = db.scalar(
        select(UserSession)
        .where(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
        )
        .with_for_update()
    )
    now = datetime.now(timezone.utc)
    if (
        user_session is None
        or user_session.revoked_at is not None
        or user_session.expires_at <= now
        or user_session.refresh_token_hash != hash_refresh_token(payload.refresh_token)
    ):
        raise invalid_credentials

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise invalid_credentials

    user_session.revoked_at = now
    tokens = issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    current_user.session_version += 1
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == current_user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.commit()


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha atual está incorreta",
        )
    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha precisa ser diferente da atual",
        )

    current_user.password_hash = hash_password(payload.new_password)
    current_user.session_version += 1
    now = datetime.now(timezone.utc)
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == current_user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=current_user.id if current_user.role == "client" else None,
            action="change_password",
            resource="user",
            resource_id=str(current_user.id),
        )
    )
    db.commit()


@router.get("/me", response_model=UserResponse, tags=["users"])
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
