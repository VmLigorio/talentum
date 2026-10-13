# Talentum — backend/alembic/versions/0012_create_investment_positions.py
# Responsabilidade: Controla a evolução versionada do esquema do banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
"""create investment positions

Revision ID: 0012_create_investment_positions
Revises: 0011_create_market_watchlist
Create Date: 2026-09-18
"""
# Finalidade: Cria posições consolidadas de investimentos por cliente e ativo.

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0012_create_investment_positions"
down_revision: Union[str, None] = "0011_create_market_watchlist"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Aplica a mudança de esquema: Cria posições consolidadas de investimentos por cliente e ativo."""
    # Guarda o saldo consolidado por ativo e cliente. A precisão decimal permite
    # representar quantidades fracionárias e preços com várias casas decimais.
    op.create_table(
        "investment_positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("average_price", sa.Numeric(precision=20, scale=8), nullable=False),
        # Instituição de custódia e observações são metadados opcionais.
        sa.Column("institution", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # A posição pertence ao cliente e é removida junto com sua conta.
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # As consultas da carteira filtram as posições pelo cliente.
    op.create_index("ix_investment_positions_client_id", "investment_positions", ["client_id"], unique=False)


def downgrade() -> None:
    """Reverte a mudança de esquema desta revisão e remove os objetos criados."""
    # Remove primeiro o índice dependente e, em seguida, a tabela.
    op.drop_index("ix_investment_positions_client_id", table_name="investment_positions")
    op.drop_table("investment_positions")
