"""Configurações tipadas carregadas do ambiente e de um arquivo .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da API e dos mecanismos de autenticação."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "API de Gestão de Ativos"
    app_env: str = "development"
    debug: bool = False
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"
    database_url: str = "postgresql+psycopg://toner:toner@localhost:5432/asset_management"
    secret_key: str = "change-this-development-secret-before-deployment"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    refresh_token_expire_days: int = 7


@lru_cache
def get_settings() -> Settings:
    """Retorna a configuração carregada uma única vez por processo."""
    return Settings()