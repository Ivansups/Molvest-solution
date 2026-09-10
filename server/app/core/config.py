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
    # Lite для детекта хэндоффа, если OpenRouter недоступен. В API Lite = GigaChat-2.
    gigachat_classify_model: str = "GigaChat-2"
    # Имя модели POST /embeddings. Смена на другую размерность
    # (EmbeddingsGigaR = 2560) требует миграции колонки chunks.embedding.
    gigachat_embeddings_model: str = "Embeddings"
    gigachat_scope: str = "GIGACHAT_API_PERS"
    # Локально сертификат НУЦ Минцифры часто не установлен.
    gigachat_verify_ssl_certs: bool = False
    # Generate и Vision. Виджет ждёт 60 с — один вызов должен уложиться.
    gigachat_timeout: float = 40.0
    # YES/NO хэндоффа: короткий лимит, чтобы не съесть бюджет хода.
    gigachat_classify_timeout: float = 8.0
    # --- OpenRouter: лёгкая модель для классификации (handoff-детект) ---
    # Пустой ключ — классификация через GigaChat-2 (Lite), детект не выключается.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct"
    openrouter_timeout: float = 5.0
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
    # --- Bitrix24: канал сценария 1 (открытые линии) ---
    bitrix_portal_url: str = ""
    bitrix_app_user_id: str = ""
    # Ключ исходящего REST-вебхука (Base URL /rest/{app_user_id}/{token}/).
    bitrix_app_token: str = ""
    # Секрет приложения для валидации входящих событий. Пустой — fail-closed:
    # входящие события отклоняются (403).
    bitrix_application_token: str = ""
    # Код/id коннектора и линии открытой линии для исходящего imconnector.send.messages.
    bitrix_connector_id: str = ""
    bitrix_line_id: str = ""
    # OAuth локального приложения: imconnector.*/imbot.* требуют контекст
    # приложения, статический bitrix_app_token для них не подходит (см.
    # openspec/changes/bitrix24-channel/design.md, D8).
    bitrix_client_id: str = ""
    bitrix_client_secret: str = ""
    # Код бота открытой линии (imbot.register). Пустой handler URL —
    # установку не роняем, бота не регистрируем (см. design.md D13–D14).
    bitrix_bot_code: str = "molvest_support"
    bitrix_handler_base_url: str = ""
    # --- Redmine HelpDesk (сценарий 1, почта/тикет) ---
    redmine_url: str = ""
    redmine_api_key: str = ""
    redmine_imap_host: str = ""
    redmine_imap_port: int = 993
    redmine_imap_user: str = ""
    redmine_imap_password: str = ""
    redmine_smtp_host: str = ""
    redmine_smtp_port: int = 587
    redmine_smtp_user: str = ""
    redmine_smtp_password: str = ""
    redmine_smtp_from: str = ""

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
