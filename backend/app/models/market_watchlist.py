# Talentum — backend/app/models/market_watchlist.py
# Responsabilidade: Define os modelos ORM que representam as entidades persistidas no banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class MarketWatchlistItem(Base):
    """Ativo acompanhado por um cliente na lista de observação."""
    __tablename__ = "market_watchlist_items"
    __table_args__ = (UniqueConstraint("client_id", "symbol", "market", name="uq_market_watchlist_client_symbol_market"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # A constraint composta evita duplicar um mesmo ativo na lista do cliente.
    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Símbolo e mercado identificam o ativo; a nota guarda contexto opcional.
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
