# Talentum — backend/app/models/market_alert.py
# Responsabilidade: Define os modelos ORM que representam as entidades persistidas no banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class MarketAlert(Base):
    """Condição de preço monitorada para um ativo do cliente."""
    __tablename__ = "market_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Separa o cliente dono do alerta do usuário que o cadastrou.
    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    # Registra o mercado, mas a moeda efetiva do instrumento não é persistida.
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    # O alvo e a condição definem quando a regra de preço é atendida.
    target_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    condition: Mapped[str] = mapped_column(
        String(20), nullable=False, default="at_or_below", server_default=text("'at_or_below'")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default=text("'active'")
    )
    # Guarda a última observação e quando a condição foi disparada.
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
