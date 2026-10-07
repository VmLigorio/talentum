# Talentum — backend/alembic/versions/0015_document_review_alerts.py
# Responsabilidade: Controla a evolução versionada do esquema do banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
"""add annual document review notification preference

Revision ID: 0015_document_review_alerts
Revises: 0014_profile_documents
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0015_document_review_alerts"
down_revision: Union[str, None] = "0014_profile_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column(
            "document_review_due",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("notification_preferences", "document_review_due")
