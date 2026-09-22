"""create client profiles permissions and audit logs

Revision ID: 0003_create_client_access
Revises: 0002_create_sessions
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_create_client_access"
down_revision: Union[str, None] = "0002_create_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("advisor_id", sa.Integer(), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["advisor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_client_profiles_user_id", "client_profiles", ["user_id"], unique=False)
    op.create_index("ix_client_profiles_advisor_id", "client_profiles", ["advisor_id"], unique=False)

    op.create_table(
        "client_permissions",
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("can_edit_profile", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("can_edit_financial_profile", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("can_edit_patrimony", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("can_edit_goals", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("can_upload_documents", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("client_id"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("client_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("resource", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["client_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"], unique=False)
    op.create_index("ix_audit_logs_client_user_id", "audit_logs", ["client_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_client_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("client_permissions")
    op.drop_index("ix_client_profiles_advisor_id", table_name="client_profiles")
    op.drop_index("ix_client_profiles_user_id", table_name="client_profiles")
    op.drop_table("client_profiles")
