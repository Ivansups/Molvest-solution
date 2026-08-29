"""Конфигурация приложения из переменных окружения."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, читаются из .env / окружения."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gigachat_api_key: str = ""
    gigachat_api_url: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/molvest"
    confidence_threshold: float = 0.8
    top_k: int = 5
    max_chunk_size: int = 512
    internal_service_token: str = ""


settings = Settings()
