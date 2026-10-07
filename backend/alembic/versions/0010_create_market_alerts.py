# Talentum — backend/alembic/versions/0010_create_market_alerts.py
# Responsabilidade: Controla a evolução versionada do esquema do banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
"""create market price alerts

Revision ID: 0010_create_market_alerts
Revises: 0009_notification_prefs
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_create_market_alerts"
down_revision: Union[str, None] = "0009_notification_prefs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column("market_price_alert", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_table(
        "market_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=10), nullable=False),
        sa.Column("target_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("condition", sa.String(length=20), server_default=sa.text("'at_or_below'"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("last_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_alerts_client_id", "market_alerts", ["client_id"], unique=False)
    op.create_index("ix_market_alerts_created_by_user_id", "market_alerts", ["created_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_market_alerts_created_by_user_id", table_name="market_alerts")
    op.drop_index("ix_market_alerts_client_id", table_name="market_alerts")
    op.drop_table("market_alerts")
    op.drop_column("notification_preferences", "market_price_alert")
