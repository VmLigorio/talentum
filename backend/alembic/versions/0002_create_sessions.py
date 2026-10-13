# Talentum — backend/alembic/versions/0002_create_sessions.py
# Responsabilidade: Controla a evolução versionada do esquema do banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
"""create sessions table

Revision ID: 0002_create_sessions
Revises: 0001_create_users
Create Date: 2026-09-17
"""
# Finalidade: Cria o armazenamento de sessões renováveis e sua expiração ou revogação.

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_create_sessions"
down_revision: Union[str, None] = "0001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Aplica a mudança de esquema: Cria o armazenamento de sessões renováveis e sua expiração ou revogação."""
    # Guarda somente o hash do refresh token, com validade e instante de revogação.
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Acelera a busca das sessões vinculadas a cada conta.
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)


def downgrade() -> None:
    """Reverte a mudança de esquema desta revisão e remove os objetos criados."""
    # Remove o índice dependente antes de eliminar a tabela de sessões.
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
