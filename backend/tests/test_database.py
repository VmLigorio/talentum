# Talentum — backend/tests/test_database.py
# Responsabilidade: Contém testes automatizados que protegem o comportamento esperado do sistema.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from app.db.database import Base
from app.models import User


def test_user_model_is_registered_in_metadata() -> None:
    """Verifica o registro do modelo de usuário nos metadados ORM."""
    assert User.__tablename__ == "users"
    assert "users" in Base.metadata.tables


def test_user_model_has_required_identity_fields() -> None:
    """Verifica os campos obrigatórios de identidade da conta."""
    columns = User.__table__.c

    assert columns.email.unique is True
    assert columns.name.nullable is False
    assert columns.password_hash.nullable is False


def test_client_access_models_are_registered_in_metadata() -> None:
    """Verifica o registro dos modelos de perfil, permissão e auditoria."""
    assert {"client_profiles", "client_permissions", "audit_logs"}.issubset(
        Base.metadata.tables
    )


def test_financial_models_are_registered_in_metadata() -> None:
    """Verifica o registro dos modelos financeiros no banco."""
    assert {"financial_profiles", "patrimony_items", "goals"}.issubset(
        Base.metadata.tables
    )


def test_report_model_is_registered_in_metadata() -> None:
    """Verifica o registro do modelo de relatório."""
    assert "reports" in Base.metadata.tables


def test_document_model_is_registered_in_metadata() -> None:
    """Verifica o registro do modelo de documento."""
    assert "documents" in Base.metadata.tables


def test_notification_model_is_registered_in_metadata() -> None:
    """Verifica o registro do modelo de notificação."""
    assert "notifications" in Base.metadata.tables


def test_notification_preference_model_is_registered_in_metadata() -> None:
    """Verifica o registro do modelo de preferências de notificação."""
    assert "notification_preferences" in Base.metadata.tables


def test_market_alert_model_is_registered_in_metadata() -> None:
    """Verifica o registro do modelo de alertas de mercado."""
    assert "market_alerts" in Base.metadata.tables


def test_market_watchlist_model_is_registered_in_metadata() -> None:
    """Verifica o registro do modelo da lista de acompanhamento."""
    assert "market_watchlist_items" in Base.metadata.tables


def test_investment_position_model_is_registered_in_metadata() -> None:
    """Verifica o registro do modelo de posição de investimento."""
    assert "investment_positions" in Base.metadata.tables
    assert "name" in Base.metadata.tables["investment_positions"].c


def test_portfolio_snapshot_model_is_registered_in_metadata() -> None:
    """Verifica o registro do modelo de fotografia histórica da carteira."""
    assert "portfolio_snapshots" in Base.metadata.tables
