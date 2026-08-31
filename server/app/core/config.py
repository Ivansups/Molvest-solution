"""Конфигурация приложения из переменных окружения."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, читаются из .env / окружения."""

    # Сначала server/.env, затем корневой .env (запуск из server/).
    # Переменные окружения (в т.ч. из docker compose env_file) имеют приоритет.
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    gigachat_api_key: str = ""
    gigachat_api_url: str = ""
    gigachat_model: str = "GigaChat-2"
    gigachat_scope: str = "GIGACHAT_API_PERS"
    # Локально сертификат НУЦ Минцифры часто не установлен.
    gigachat_verify_ssl_certs: bool = False
    gigachat_timeout: float = 60.0
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/molvest"
    redis_url: str = "redis://redis:6379/0"
    confidence_threshold: float = 0.8
    top_k: int = 5
    max_chunk_size: int = 512
    chunk_overlap: int = 128
    upload_dir: str = "./data/uploads"
    internal_service_token: str = ""


settings = Settings()
