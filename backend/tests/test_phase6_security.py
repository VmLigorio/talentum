import pytest

from app.api.documents import safe_original_name
from app.core.config import Settings
from app.core.rate_limit import LoginRateLimiter


def test_production_settings_reject_development_secrets() -> None:
    with pytest.raises(ValueError):
        Settings(environment="production")


def test_production_settings_accept_explicit_secure_values() -> None:
    settings = Settings(
        environment="production",
        jwt_secret="a" * 48,
        database_url="postgresql+psycopg://app:strong-password@db/talentum",
        cors_origins="https://advisor.example.com",
        trusted_hosts="api.example.com",
    )

    assert settings.api_docs_enabled is True


def test_login_rate_limiter_blocks_and_resets() -> None:
    limiter = LoginRateLimiter(attempts=2, window_seconds=60)

    assert limiter.allow("ip:email")
    limiter.register_failure("ip:email")
    assert limiter.allow("ip:email")
    limiter.register_failure("ip:email")
    assert not limiter.allow("ip:email")
    limiter.reset("ip:email")
    assert limiter.allow("ip:email")


def test_uploaded_filename_is_safe_for_headers_and_paths() -> None:
    assert safe_original_name("../../relatorio\r\n.pdf") == "relatorio__.pdf"
    assert safe_original_name("área financeira (2026).pdf") == "area financeira (2026).pdf"
