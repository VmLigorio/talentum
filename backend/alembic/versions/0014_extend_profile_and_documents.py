"""extend client profile and classify documents

Revision ID: 0014_profile_documents
Revises: 0013_create_portfolio_snapshots
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0014_profile_documents"
down_revision: Union[str, None] = "0013_create_portfolio_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("client_profiles", sa.Column("father_name", sa.String(length=120), nullable=True))
    op.add_column("client_profiles", sa.Column("mother_name", sa.String(length=120), nullable=True))
    op.add_column("client_profiles", sa.Column("address_street", sa.String(length=160), nullable=True))
    op.add_column("client_profiles", sa.Column("address_number", sa.String(length=30), nullable=True))
    op.add_column("client_profiles", sa.Column("address_city", sa.String(length=100), nullable=True))
    op.add_column("client_profiles", sa.Column("address_zip_code", sa.String(length=20), nullable=True))
    op.add_column("client_profiles", sa.Column("address_state", sa.String(length=60), nullable=True))
    op.add_column(
        "documents",
        sa.Column("kind", sa.String(length=30), server_default=sa.text("'other'"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("documents", "kind")
    op.drop_column("client_profiles", "address_state")
    op.drop_column("client_profiles", "address_zip_code")
    op.drop_column("client_profiles", "address_city")
    op.drop_column("client_profiles", "address_number")
    op.drop_column("client_profiles", "address_street")
    op.drop_column("client_profiles", "mother_name")
    op.drop_column("client_profiles", "father_name")
