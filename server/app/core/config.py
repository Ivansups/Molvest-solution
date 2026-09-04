"""Конфигурация приложения из переменных окружения."""

from typing import Literal

from pydantic import field_validator
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
    # Имя модели POST /embeddings. Смена на другую размерность
    # (EmbeddingsGigaR = 2560) требует миграции колонки chunks.embedding.
    gigachat_embeddings_model: str = "Embeddings"
    gigachat_scope: str = "GIGACHAT_API_PERS"
    # Локально сертификат НУЦ Минцифры часто не установлен.
    gigachat_verify_ssl_certs: bool = False
    gigachat_timeout: float = 60.0
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/molvest"
    redis_url: str = "redis://redis:6379/0"
    confidence_threshold: float = 0.8
    top_k: int = 5
    # 512 слов ≈ 900 токенов, окно Embeddings — 512. Держим запас.
    max_chunk_size: int = 180
    chunk_overlap: int = 40
    upload_dir: str = "./data/uploads"
    internal_service_token: str = ""
    # draft — generate только по кнопке оператора; auto — агент может ответить гостю.
    operator_assist_mode: Literal["draft", "auto"] = "draft"

    @field_validator("gigachat_embeddings_model")
    @classmethod
    def embeddings_model_not_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("GIGACHAT_EMBEDDINGS_MODEL не должен быть пустым")
        return stripped

    @field_validator("operator_assist_mode", mode="before")
    @classmethod
    def assist_mode_normalize(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


settings = Settings()
