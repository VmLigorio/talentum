# Talentum — backend/alembic/versions/0017_investment_position_name.py
# Responsabilidade: Controla a evolução versionada do esquema do banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
"""add editable investment position name

Revision ID: 0017_investment_position_name
Revises: 0016_suitability_assessments
Create Date: 2026-09-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0017_investment_position_name"
down_revision: Union[str, None] = "0016_suitability_assessments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "investment_positions",
        sa.Column("name", sa.String(length=160), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("investment_positions", "name")
