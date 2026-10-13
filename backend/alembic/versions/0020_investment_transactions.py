# Talentum — backend/alembic/versions/0020_investment_transactions.py
"""create append-only investment transaction history

Revision ID: 0020_investment_transactions
Revises: 0019_suitability_finance
Create Date: 2026-10-06
"""
# Finalidade: Cria o histórico append-only de operações e metadados de cancelamento.

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0020_investment_transactions"
down_revision: Union[str, None] = "0019_suitability_finance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Aplica a mudança de esquema: Cria o histórico append-only de operações e metadados de cancelamento."""
    # Guarda valores da operação e o saldo/custo médio antes e depois para reconstrução histórica.
    op.create_table(
        "investment_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        # O cliente é obrigatório; posição e autores podem desaparecer sem
        # apagar o registro histórico, preservando seus dados descritivos.
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("position_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        # Tipo, ativo, mercado, moeda e data identificam a operação registrada.
        sa.Column("operation_type", sa.String(length=10), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("market", sa.String(length=10), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("operation_date", sa.Date(), nullable=False),
        # Valores monetários e quantidades usam precisão decimal fixa; vendas
        # podem ainda guardar lucro realizado e o custo médio aplicado.
        sa.Column("quantity", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("gross_value", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("fees", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("net_value", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("quantity_before", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("average_price_before", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("quantity_after", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("average_price_after", sa.Numeric(precision=20, scale=8), nullable=True),
        # Dados de custódia/anotação não são obrigatórios para registrar o trade.
        sa.Column("institution", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        # Anulação é representada por metadados em vez de excluir a operação.
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by_user_id", sa.Integer(), nullable=True),
        sa.Column("void_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Restringe tipos, mercados e valores; referências opcionais preservam histórico após exclusões.
        sa.CheckConstraint("operation_type IN ('buy', 'sell')", name="ck_investment_transaction_type"),
        sa.CheckConstraint("market IN ('br', 'global')", name="ck_investment_transaction_market"),
        sa.CheckConstraint("quantity > 0 AND unit_price > 0 AND fees >= 0", name="ck_investment_transaction_amounts"),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["position_id"], ["investment_positions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["voided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Acelera listagens por cliente, posição e ordenação cronológica determinística.
    op.create_index("ix_investment_transactions_client_id", "investment_transactions", ["client_id"])
    op.create_index("ix_investment_transactions_position_id", "investment_transactions", ["position_id"])
    op.create_index(
        "ix_investment_transactions_client_date",
        "investment_transactions",
        ["client_id", "operation_date", "id"],
    )


def downgrade() -> None:
    """Reverte a mudança de esquema desta revisão e remove os objetos criados."""
    # Remove primeiro os índices dependentes da tabela e depois o histórico criado.
    op.drop_index("ix_investment_transactions_client_date", table_name="investment_transactions")
    op.drop_index("ix_investment_transactions_position_id", table_name="investment_transactions")
    op.drop_index("ix_investment_transactions_client_id", table_name="investment_transactions")
    op.drop_table("investment_transactions")
