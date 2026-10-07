# Talentum — backend/alembic/versions/0013_create_portfolio_snapshots.py
# Responsabilidade: Controla a evolução versionada do esquema do banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
"""create portfolio snapshots

Revision ID: 0013_create_portfolio_snapshots
Revises: 0012_create_investment_positions
Create Date: 2026-09-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_create_portfolio_snapshots"
down_revision: Union[str, None] = "0012_create_investment_positions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("invested_total", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("current_total", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("pnl_total", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("position_count", sa.Integer(), nullable=False),
        sa.Column("priced_position_count", sa.Integer(), nullable=False),
        sa.Column("source_status", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolio_snapshots_client_id", "portfolio_snapshots", ["client_id"], unique=False)
    op.create_index("ix_portfolio_snapshots_captured_at", "portfolio_snapshots", ["captured_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_portfolio_snapshots_captured_at", table_name="portfolio_snapshots")
    op.drop_index("ix_portfolio_snapshots_client_id", table_name="portfolio_snapshots")
    op.drop_table("portfolio_snapshots")
