"""Единый JSON-ответ на ошибки FastAPI."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var

logger = logging.getLogger(__name__)


def error_envelope(
    *,
    error: str,
    detail: str,
    status_code: int,
) -> JSONResponse:
    """Собирает {error, detail, request_id} и дублирует id в заголовок."""
    request_id = request_id_var.get()
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "detail": detail, "request_id": request_id},
        headers={"x-request-id": request_id},
    )


def register_error_handlers(app: FastAPI) -> None:
    """HTTP и валидация — в конверт; 500 логирует стек, клиенту его не отдаёт."""

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        del request
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return error_envelope(
            error="http_error",
            detail=detail,
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del request, exc
        return error_envelope(
            error="http_error",
            detail="Ошибка валидации запроса",
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        del request
        logger.exception("непойманное исключение", exc_info=exc)
        return error_envelope(
            error="internal_error",
            detail="Внутренняя ошибка сервера",
            status_code=500,
        )
