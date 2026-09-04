"""Точка входа FastAPI-приложения."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.core.config import settings
from app.core.errors import error_envelope, register_error_handlers
from app.core.logging import request_id_var, setup_logging

setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Предупреждает, если API слушает без служебного токена."""
    if not settings.internal_service_token:
        logger.warning(
            "INTERNAL_SERVICE_TOKEN пуст: служебные маршруты открыты без токена"
        )
    yield


app = FastAPI(title="Molvest AI-Agent API", lifespan=lifespan)
register_error_handlers(app)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(conversations_router)
app.include_router(metrics_router)

_SKIP_ACCESS_LOG = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})


@app.middleware("http")
async def log_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Пишет request_id и пару запрос/ответ. /health не засоряет лог."""
    request_id = request.headers.get("x-request-id") or str(uuid4())
    token = request_id_var.set(request_id)
    path = request.url.path
    try:
        if path not in _SKIP_ACCESS_LOG:
            logger.info("запрос %s %s", request.method, path)
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("сбой %s %s", request.method, path)
            return error_envelope(
                error="internal_error",
                detail="Внутренняя ошибка сервера",
                status_code=500,
            )
        if path not in _SKIP_ACCESS_LOG:
            logger.info(
                "ответ %s %s status=%s",
                request.method,
                path,
                response.status_code,
            )
        response.headers["x-request-id"] = request_id
        return response
    finally:
        request_id_var.reset(token)
