"""Эндпоинт проверки живости сервиса."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Возвращает статус сервиса."""
    return {"status": "ok"}
