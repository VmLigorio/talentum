# Talentum — backend/app/models/investment_transaction.py
# Livro append-only de compras e vendas registradas na carteira.
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class InvestmentTransaction(Base):
    """Registro de uma operação e de seus efeitos sobre a posição do cliente.

    Quantidades anteriores e posteriores preservam o histórico da posição; o
    cancelamento é registrado por metadados, sem apagar a operação original.
    """

    __tablename__ = "investment_transactions"
    __table_args__ = (
        CheckConstraint("operation_type IN ('buy', 'sell')", name="ck_investment_transaction_type"),
        CheckConstraint("market IN ('br', 'global')", name="ck_investment_transaction_market"),
        CheckConstraint("quantity > 0 AND unit_price > 0 AND fees >= 0", name="ck_investment_transaction_amounts"),
        Index("ix_investment_transactions_client_date", "client_id", "operation_date", "id"),
    )

    # Identificam o cliente, a posição vinculada e os usuários envolvidos;
    # posição e autores podem ser desvinculados sem apagar o histórico.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position_id: Mapped[int | None] = mapped_column(
        ForeignKey("investment_positions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Preservam a identidade do ativo e os dados informados na data da operação.
    operation_type: Mapped[str] = mapped_column(String(10), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    operation_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Valores de entrada e saldos antes/depois permitem auditar a atualização
    # do preço médio e o resultado realizado sem consultar a cotação atual.
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    gross_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=Decimal("0"))
    net_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    quantity_before: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    average_price_before: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    quantity_after: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    average_price_after: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    # Metadados opcionais de custódia e justificativa da operação.
    institution: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # A anulação fica registrada no próprio item para manter o histórico auditável.
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
