# Talentum — backend/app/models/user.py
# Responsabilidade: Define os modelos ORM que representam as entidades persistidas no banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class User(Base):
    """Conta de acesso do cliente, assessor ou administrador."""
    __tablename__ = "users"

    # Chave referenciada pelos vínculos de cliente, auditoria e sessões autenticadas.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Identidade de acesso; o e-mail é único no banco e a senha só é persistida como hash.
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Papel, ativação e versão da sessão controlam acesso e invalidação de tokens.
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="client",
        server_default=text("'client'"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    session_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    # Datas de ciclo de vida são geradas pelo banco e atualizadas nas alterações.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
