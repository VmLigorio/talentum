# Talentum — backend/alembic/versions/0007_create_documents.py
# Responsabilidade: Controla a evolução versionada do esquema do banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
"""create client documents

Revision ID: 0007_create_documents
Revises: 0006_create_action_plan
Create Date: 2026-09-18
"""
# Finalidade: Cria metadados para documentos enviados aos clientes.

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_create_documents"
down_revision: Union[str, None] = "0006_create_action_plan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Aplica a mudança de esquema: Cria metadados para documentos enviados aos clientes."""
    # Guarda metadados e nomes de armazenamento; o conteúdo binário fica no sistema de arquivos.
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        # Impede excluir o usuário que consta como autor enquanto o documento o referencia.
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name"),
    )
    # Apoia listagens por cliente e consultas dos documentos enviados por usuário.
    op.create_index("ix_documents_client_id", "documents", ["client_id"], unique=False)
    op.create_index("ix_documents_uploaded_by_user_id", "documents", ["uploaded_by_user_id"], unique=False)


def downgrade() -> None:
    """Reverte a mudança de esquema desta revisão e remove os objetos criados."""
    # Remove os índices dependentes antes de remover os metadados dos documentos.
    op.drop_index("ix_documents_uploaded_by_user_id", table_name="documents")
    op.drop_index("ix_documents_client_id", table_name="documents")
    op.drop_table("documents")
