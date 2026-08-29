"""Точка входа FastAPI-приложения."""

from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title="Molvest AI-Agent API")

app.include_router(health_router)
app.include_router(chat_router)
