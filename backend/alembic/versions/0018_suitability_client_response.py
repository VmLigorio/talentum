# Talentum — backend/alembic/versions/0018_suitability_client_response.py
"""record client response to an approved suitability recommendation

Revision ID: 0018_suitability_client_response
Revises: 0017_investment_position_name
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0018_suitability_client_response"
down_revision: Union[str, None] = "0017_investment_position_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "suitability_assessments",
        sa.Column(
            "client_response",
            sa.String(length=30),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.add_column(
        "suitability_assessments",
        sa.Column("client_response_note", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "suitability_assessments",
        sa.Column("client_response_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("suitability_assessments", "client_response_at")
    op.drop_column("suitability_assessments", "client_response_note")
    op.drop_column("suitability_assessments", "client_response")
