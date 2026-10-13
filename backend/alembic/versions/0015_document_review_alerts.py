# Talentum — backend/alembic/versions/0015_document_review_alerts.py
# Responsabilidade: Controla a evolução versionada do esquema do banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
"""add annual document review notification preference

Revision ID: 0015_document_review_alerts
Revises: 0014_profile_documents
Create Date: 2026-09-20
"""
# Finalidade: Adiciona a preferência para avisos de revisão anual de documentos.

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0015_document_review_alerts"
down_revision: Union[str, None] = "0014_profile_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Aplica a mudança de esquema: Adiciona a preferência para avisos de revisão anual de documentos."""
    # Ativa o aviso para usuários atuais e futuros por padrão; a preferência
    # pode ser desativada individualmente pelo titular da conta.
    op.add_column(
        "notification_preferences",
        sa.Column(
            "document_review_due",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Reverte a mudança de esquema desta revisão e remove os objetos criados."""
    # A reversão remove a configuração de aviso de revisão anual.
    op.drop_column("notification_preferences", "document_review_due")
