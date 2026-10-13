# Talentum — backend/alembic/versions/0006_create_action_plan.py
# Responsabilidade: Controla a evolução versionada do esquema do banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
"""create client action plan

Revision ID: 0006_create_action_plan
Revises: 0005_create_reports
Create Date: 2026-09-18
"""
# Finalidade: Cria tarefas e ações do plano de acompanhamento do cliente.

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_create_action_plan"
down_revision: Union[str, None] = "0005_create_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Aplica a mudança de esquema: Cria tarefas e ações do plano de acompanhamento do cliente."""
    # Associa cada ação ao cliente e mantém opcional o vínculo com uma meta específica.
    op.create_table(
        "action_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'planned'"), nullable=False),
        sa.Column("priority", sa.String(length=20), server_default=sa.text("'medium'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Facilita consultas de ações por cliente e por meta.
    op.create_index("ix_action_items_client_id", "action_items", ["client_id"], unique=False)
    op.create_index("ix_action_items_goal_id", "action_items", ["goal_id"], unique=False)


def downgrade() -> None:
    """Reverte a mudança de esquema desta revisão e remove os objetos criados."""
    # Remove índices e tabela na ordem inversa à criação.
    op.drop_index("ix_action_items_goal_id", table_name="action_items")
    op.drop_index("ix_action_items_client_id", table_name="action_items")
    op.drop_table("action_items")
