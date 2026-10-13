# Talentum — backend/alembic/versions/0011_create_market_watchlist.py
# Responsabilidade: Controla a evolução versionada do esquema do banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
"""create market watchlist

Revision ID: 0011_create_market_watchlist
Revises: 0010_create_market_alerts
Create Date: 2026-09-19
"""
# Finalidade: Cria a lista de ativos que cada cliente acompanha.

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_create_market_watchlist"
down_revision: Union[str, None] = "0010_create_market_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Aplica a mudança de esquema: Cria a lista de ativos que cada cliente acompanha."""
    # Cada registro representa um ativo observado por um cliente e identifica
    # o usuário responsável por cadastrá-lo; a nota é opcional.
    op.create_table(
        "market_watchlist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=10), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Ao excluir o cliente, seus itens deixam de existir; o autor não pode
        # ser removido enquanto houver registros que dependam de sua autoria.
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        # Impede que o mesmo cliente acompanhe duas vezes o mesmo ativo no
        # mesmo mercado, sem bloquear o símbolo em outras carteiras.
        sa.UniqueConstraint("client_id", "symbol", "market", name="uq_market_watchlist_client_symbol_market"),
    )
    # Índices aceleram listagens por cliente e consultas pelo usuário autor.
    op.create_index("ix_market_watchlist_items_client_id", "market_watchlist_items", ["client_id"], unique=False)
    op.create_index("ix_market_watchlist_items_created_by_user_id", "market_watchlist_items", ["created_by_user_id"], unique=False)


def downgrade() -> None:
    """Reverte a mudança de esquema desta revisão e remove os objetos criados."""
    # Índices são removidos antes da tabela que os contém.
    op.drop_index("ix_market_watchlist_items_created_by_user_id", table_name="market_watchlist_items")
    op.drop_index("ix_market_watchlist_items_client_id", table_name="market_watchlist_items")
    op.drop_table("market_watchlist_items")
