"""Точка входа FastAPI-приложения."""

import logging
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.core.logging import request_id_var, setup_logging

setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI(title="Molvest AI-Agent API")

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(documents_router)

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
            raise
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
