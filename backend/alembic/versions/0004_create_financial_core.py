"""create financial profile patrimony items and goals

Revision ID: 0004_create_financial_core
Revises: 0003_create_client_access
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_create_financial_core"
down_revision: Union[str, None] = "0003_create_client_access"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "financial_profiles",
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("monthly_income", sa.Numeric(14, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("monthly_expenses", sa.Numeric(14, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("risk_profile", sa.String(length=30), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("client_id"),
    )

    op.create_table(
        "patrimony_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=160), nullable=False),
        sa.Column("institution", sa.String(length=120), nullable=True),
        sa.Column("value", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patrimony_items_client_id", "patrimony_items", ["client_id"], unique=False)

    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("target_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("current_value", sa.Numeric(14, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_goals_client_id", "goals", ["client_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_goals_client_id", table_name="goals")
    op.drop_table("goals")
    op.drop_index("ix_patrimony_items_client_id", table_name="patrimony_items")
    op.drop_table("patrimony_items")
    op.drop_table("financial_profiles")
