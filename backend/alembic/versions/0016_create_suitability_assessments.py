# Talentum — backend/alembic/versions/0016_create_suitability_assessments.py
# Responsabilidade: Cria o histórico de questionários e carteiras sugeridas.
"""create suitability assessments

Revision ID: 0016_suitability_assessments
Revises: 0015_document_review_alerts
Create Date: 2026-09-24
"""
# Finalidade: Cria o histórico de respostas, pontuação e carteira sugerida do suitability.

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0016_suitability_assessments"
down_revision: Union[str, None] = "0015_document_review_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Aplica a mudança de esquema: Cria o histórico de respostas, pontuação e carteira sugerida do suitability."""
    # Cada avaliação preserva respostas e recomendação estruturadas para
    # consulta posterior; ambos os campos podem conter informações financeiras.
    op.create_table(
        "suitability_assessments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        # Objetivo, perfil e pontuação registram o resultado calculado do questionário.
        sa.Column("objective", sa.String(length=30), nullable=False),
        sa.Column("risk_profile", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommendation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        # A avaliação nasce aguardando revisão e tem prazo de validade explícito.
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending_review'"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        # A revisão é opcional; excluir o assessor revisor preserva o registro
        # e limpa apenas a referência de autoria da revisão.
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        # A conta do cliente é dona do histórico; a referência ao revisor é opcional.
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Atende às consultas do histórico filtradas pela conta do cliente.
    op.create_index(
        "ix_suitability_assessments_client_id",
        "suitability_assessments",
        ["client_id"],
        unique=False,
    )


def downgrade() -> None:
    """Reverte a mudança de esquema desta revisão e remove os objetos criados."""
    # Remove primeiro o índice e então todo o histórico de avaliações.
    op.drop_index("ix_suitability_assessments_client_id", table_name="suitability_assessments")
    op.drop_table("suitability_assessments")
