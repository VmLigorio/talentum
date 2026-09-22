from app.db.database import Base
from app.models import User


def test_user_model_is_registered_in_metadata() -> None:
    assert User.__tablename__ == "users"
    assert "users" in Base.metadata.tables


def test_user_model_has_required_identity_fields() -> None:
    columns = User.__table__.c

    assert columns.email.unique is True
    assert columns.name.nullable is False
    assert columns.password_hash.nullable is False


def test_client_access_models_are_registered_in_metadata() -> None:
    assert {"client_profiles", "client_permissions", "audit_logs"}.issubset(
        Base.metadata.tables
    )


def test_financial_models_are_registered_in_metadata() -> None:
    assert {"financial_profiles", "patrimony_items", "goals"}.issubset(
        Base.metadata.tables
    )


def test_report_model_is_registered_in_metadata() -> None:
    assert "reports" in Base.metadata.tables


def test_document_model_is_registered_in_metadata() -> None:
    assert "documents" in Base.metadata.tables


def test_notification_model_is_registered_in_metadata() -> None:
    assert "notifications" in Base.metadata.tables


def test_notification_preference_model_is_registered_in_metadata() -> None:
    assert "notification_preferences" in Base.metadata.tables


def test_market_alert_model_is_registered_in_metadata() -> None:
    assert "market_alerts" in Base.metadata.tables


def test_market_watchlist_model_is_registered_in_metadata() -> None:
    assert "market_watchlist_items" in Base.metadata.tables


def test_investment_position_model_is_registered_in_metadata() -> None:
    assert "investment_positions" in Base.metadata.tables


def test_portfolio_snapshot_model_is_registered_in_metadata() -> None:
    assert "portfolio_snapshots" in Base.metadata.tables
