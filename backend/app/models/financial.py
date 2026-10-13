# Talentum — backend/app/models/financial.py
# Responsabilidade: Define os modelos ORM que representam as entidades persistidas no banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class FinancialProfile(Base):
    """Renda, despesas e perfil de risco registrados para o cliente."""
    __tablename__ = "financial_profiles"

    # Um registro por cliente, com valores declarados e perfil de risco atual.
    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    monthly_income: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    monthly_expenses: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    risk_profile: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Atualiza a referência temporal quando renda, despesas ou risco mudam.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PatrimonyItem(Base):
    """Bem ou recurso que compõe o patrimônio declarado pelo cliente."""
    __tablename__ = "patrimony_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Cada item pertence ao cliente e mantém sua própria categoria e descrição.
    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(String(160), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Valor declarado e observações complementares do item.
    value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Datas automáticas registram criação e alteração do cadastro.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Goal(Base):
    """Meta financeira e valores usados para acompanhar seu progresso."""
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # A meta pertence ao cliente e mantém alvo, progresso e prazo separados.
    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    target_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    current_value: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # O estado acompanha o ciclo da meta; datas registram sua manutenção.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default=text("'active'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
