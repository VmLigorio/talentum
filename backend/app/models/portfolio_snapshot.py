# Talentum — backend/app/models/portfolio_snapshot.py
# Responsabilidade: Define os modelos ORM que representam as entidades persistidas no banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    invested_total: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    current_total: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    pnl_total: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    position_count: Mapped[int] = mapped_column(Integer, nullable=False)
    priced_position_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_status: Mapped[str] = mapped_column(String(20), nullable=False)
