"""Единый JSON-ответ на ошибки FastAPI."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var


def error_envelope(
    *,
    error: str,
    detail: str,
    status_code: int,
) -> JSONResponse:
    """JSON с error, detail и request_id плюс заголовок x-request-id."""
    request_id = request_id_var.get()
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "detail": detail, "request_id": request_id},
        headers={"x-request-id": request_id},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Вешает обработчики HTTP, валидации и непойманных исключений."""

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
        del request, exc
        return error_envelope(
            error="internal_error",
            detail="Внутренняя ошибка сервера",
            status_code=500,
        )
