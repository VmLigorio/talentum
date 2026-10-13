"""Remove legacy audit JSON that may contain personal and financial data."""

from alembic import op


revision = "0021_redact_audit_log_details"
down_revision = "0020_investment_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Preserve event metadata while erasing duplicated sensitive payloads."""
    op.execute("UPDATE audit_logs SET details = NULL WHERE details IS NOT NULL")


def downgrade() -> None:
    """Prevent a misleading rollback because erased payloads cannot be recovered."""
    raise RuntimeError("A redação de detalhes da auditoria é irreversível")
