from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = (
        "postgresql+psycopg://talentum_user:change-me@localhost:5432/talentum"
    )
    jwt_secret: str = "change-me-with-a-long-random-secret"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    cors_origins: str = "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8080,http://localhost:8080"
    storage_dir: str = "storage"
    brapi_base_url: str = "https://brapi.dev"
    brapi_token: str | None = None
    yahoo_finance_base_url: str = "https://query1.finance.yahoo.com"
    market_data_timeout_seconds: float = 8.0
    market_retry_attempts: int = 1
    market_cache_ttl_seconds: int = 60
    market_alert_check_interval_seconds: int = 300
    portfolio_snapshot_interval_seconds: int = 3600
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300
    max_request_body_bytes: int = 12 * 1024 * 1024
    trusted_hosts: str = "127.0.0.1,localhost,testserver"
    api_docs_enabled: bool = True
    redis_url: str | None = None
    redis_required: bool = False
    clamav_host: str | None = None
    clamav_port: int = 3310
    clamav_required: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        environment = self.environment.strip().lower()
        if self.login_rate_limit_attempts < 1 or self.login_rate_limit_window_seconds < 1:
            raise ValueError("Os limites de login precisam ser positivos")
        if self.market_retry_attempts < 0 or self.market_cache_ttl_seconds < 0:
            raise ValueError("As configurações de resiliência de mercado não podem ser negativas")
        if self.max_request_body_bytes < 1024 * 1024:
            raise ValueError("O limite de requisição precisa ser de pelo menos 1 MB")
        if environment in {"production", "prod"}:
            if len(self.jwt_secret) < 32 or any(marker in self.jwt_secret for marker in ("change-me", "GERE_UM", "COLOQUE")):
                raise ValueError("JWT_SECRET precisa ser um segredo aleatório de pelo menos 32 caracteres")
            if any(marker in self.database_url for marker in ("change-me", "talentum_dev_password", "COLOQUE", "seudominio")):
                raise ValueError("DATABASE_URL ainda usa credenciais de desenvolvimento")
            if any(origin.strip().lower().startswith("http://") for origin in self.cors_origins.split(",")):
                raise ValueError("CORS_ORIGINS não pode usar HTTP em produção")
            if not self.trusted_hosts.strip() or "seudominio" in self.trusted_hosts:
                raise ValueError("TRUSTED_HOSTS precisa ser configurado em produção")
            if self.redis_required and not self.redis_url:
                raise ValueError("REDIS_URL precisa ser configurado quando REDIS_REQUIRED=true")
            if self.clamav_required and not self.clamav_host:
                raise ValueError("CLAMAV_HOST precisa ser configurado quando CLAMAV_REQUIRED=true")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_cors_origins() -> list[str]:
    return [origin.strip() for origin in get_settings().cors_origins.split(",") if origin.strip()]


def get_trusted_hosts() -> list[str]:
    return [host.strip() for host in get_settings().trusted_hosts.split(",") if host.strip()]
