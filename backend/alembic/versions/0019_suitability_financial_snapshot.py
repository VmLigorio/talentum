# Talentum — backend/alembic/versions/0019_suitability_financial_snapshot.py
"""store the confirmed financial context used for suitability

Revision ID: 0019_suitability_finance
Revises: 0018_suitability_client_response
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0019_suitability_finance"
down_revision: Union[str, None] = "0018_suitability_client_response"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "suitability_assessments",
        sa.Column(
            "financial_situation_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("suitability_assessments", "financial_situation_snapshot")
