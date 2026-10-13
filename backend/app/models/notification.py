# Talentum — backend/app/models/notification.py
# Responsabilidade: Define os modelos ORM que representam as entidades persistidas no banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Notification(Base):
    """Notificação persistida e seu estado de leitura pelo destinatário."""
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Distingue quem recebe o aviso do cliente a que o conteúdo se refere.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Classificação e texto compõem o conteúdo apresentado ao destinatário.
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # A constraint acima impede repetição da mesma chave para o mesmo usuário.
    dedupe_key: Mapped[str] = mapped_column(String(180), nullable=False)
    # read_at registra a leitura individual; created_at ordena a caixa de entrada.
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
