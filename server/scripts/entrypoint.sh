#!/bin/sh
# Том api_venv может отстать от lockfile — сначала зависимости, потом схема.
set -eu

echo "uv sync --frozen --no-dev"
uv sync --frozen --no-dev

echo "alembic upgrade head"
alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
