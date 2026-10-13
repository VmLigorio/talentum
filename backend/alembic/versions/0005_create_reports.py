# Talentum — backend/alembic/versions/0005_create_reports.py
# Responsabilidade: Controla a evolução versionada do esquema do banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
"""create reports table

Revision ID: 0005_create_reports
Revises: 0004_create_financial_core
Create Date: 2026-09-17
"""
# Finalidade: Cria os registros de relatórios associados aos clientes.

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_create_reports"
down_revision: Union[str, None] = "0004_create_financial_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Aplica a mudança de esquema: Cria os registros de relatórios associados aos clientes."""
    # Armazena período, resumo e estado de publicação sem gravar o arquivo exportado.
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Apoia a listagem dos relatórios de cada cliente.
    op.create_index("ix_reports_client_id", "reports", ["client_id"], unique=False)


def downgrade() -> None:
    """Reverte a mudança de esquema desta revisão e remove os objetos criados."""
    # Remove primeiro o índice que depende da tabela.
    op.drop_index("ix_reports_client_id", table_name="reports")
    op.drop_table("reports")
