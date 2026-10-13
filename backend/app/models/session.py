# Talentum — backend/app/models/session.py
# Responsabilidade: Define os modelos ORM que representam as entidades persistidas no banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UserSession(Base):
    """Sessão renovável associada a uma conta autenticada."""
    __tablename__ = "sessions"

    # Compartilha o identificador jti do refresh token para localizar e revogar a sessão.
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Define a conta proprietária; a exclusão do usuário remove também suas sessões.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Guarda somente o SHA-256 do refresh token, nunca o token reutilizável em texto puro.
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Impede a renovação depois do prazo de validade da sessão.
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    # Quando preenchido, marca o encerramento explícito do refresh token.
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Registra quando o banco criou a linha, para auditoria operacional da sessão.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
