# Talentum — backend/alembic/versions/0008_create_notifications.py
# Responsabilidade: Controla a evolução versionada do esquema do banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
"""create notifications

Revision ID: 0008_create_notifications
Revises: 0007_create_documents
Create Date: 2026-09-18
"""
# Finalidade: Cria notificações persistidas e seus identificadores de deduplicação.

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_create_notifications"
down_revision: Union[str, None] = "0007_create_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Aplica a mudança de esquema: Cria notificações persistidas e seus identificadores de deduplicação."""
    # Associa cada aviso ao destinatário e ao cliente de origem para filtragem posterior.
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=180), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # Impede repetir a mesma chave de aviso para um destinatário.
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
    )
    # Apoia a listagem por destinatário e a consulta por cliente associado.
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)
    op.create_index("ix_notifications_client_id", "notifications", ["client_id"], unique=False)


def downgrade() -> None:
    """Reverte a mudança de esquema desta revisão e remove os objetos criados."""
    # Remove primeiro os índices dependentes da tabela.
    op.drop_index("ix_notifications_client_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
