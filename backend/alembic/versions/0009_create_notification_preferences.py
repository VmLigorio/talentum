"""create notification preferences

Revision ID: 0009_notification_prefs
Revises: 0008_create_notifications
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_notification_prefs"
down_revision: Union[str, None] = "0008_create_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action_overdue", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("action_due_soon", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("goal_overdue", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("goal_due_soon", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("document_uploaded", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
