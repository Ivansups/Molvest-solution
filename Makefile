# Molvest AI-Agent — команды запуска и проверки.
# `make` без аргументов печатает справку.

.DEFAULT_GOAL := help

COMPOSE       ?= docker compose
API_URL       ?= http://localhost:8000
WEB_URL       ?= http://localhost:3000
SERVER_DIR    := server
FRONTEND_DIR  := frontend

# В Docker хост БД — сервис `db`. На машине — localhost.
LOCAL_DATABASE_URL ?= postgresql+asyncpg://postgres:postgres@localhost:5432/molvest

.PHONY: help env setup \
	up down restart logs ps health \
	db migrate \
	api frontend \
	install install-server install-frontend \
	test lint lint-server lint-frontend fmt \
	clean

help: ## Показать доступные команды
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make <target>\n\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  %-18s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@printf "\nQuick start:\n  make setup      # .env + Docker API + Postgres\n  make frontend   # Next.js на :3000 (отдельный процесс)\n\n"

# ---------------------------------------------------------------------------
# Первичная настройка
# ---------------------------------------------------------------------------

env: ## Создать .env из шаблона, если файла ещё нет
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example"; \
		echo "Fill GIGACHAT_API_KEY in .env (needed for real answers, not for /health)."; \
	else \
		echo ".env already exists — not overwritten"; \
	fi

install-server: ## Поставить Python-зависимости (uv, включая dev)
	cd $(SERVER_DIR) && uv sync --all-groups

install-frontend: ## Поставить JS-зависимости (pnpm)
	pnpm --dir $(FRONTEND_DIR) install

install: install-server install-frontend ## Поставить зависимости backend и frontend

setup: env up health ## Полный первый запуск: .env, Docker, проверка /health
	@echo ""
	@echo "API:     $(API_URL)/health"
	@echo "Docs:    $(API_URL)/docs"
	@echo "UI:      make frontend  →  $(WEB_URL)"

# ---------------------------------------------------------------------------
# Docker (API + Postgres)
# ---------------------------------------------------------------------------

up: env ## Собрать и поднять API + Postgres в фоне
	$(COMPOSE) up -d --build

down: ## Остановить контейнеры (том БД не удаляется)
	$(COMPOSE) down

restart: ## Перезапустить контейнеры
	$(COMPOSE) restart

logs: ## Логи API и Postgres (Ctrl+C — выход)
	$(COMPOSE) logs -f --tail=100

ps: ## Статус контейнеров
	$(COMPOSE) ps

db: env ## Поднять только Postgres (для локального uvicorn)
	$(COMPOSE) up -d db

migrate: env ## Применить миграции Alembic внутри контейнера API
	$(COMPOSE) exec api alembic upgrade head

health: ## Дождаться ответа API /health (до 60 с)
	@echo "Waiting for API at $(API_URL)/health ..."
	@i=0; \
	until curl -sf "$(API_URL)/health" >/dev/null; do \
		i=$$((i + 1)); \
		if [ $$i -ge 60 ]; then \
			echo "API did not become ready in 60s. Try: make logs"; \
			exit 1; \
		fi; \
		sleep 1; \
	done
	@curl -s "$(API_URL)/health" && echo

# ---------------------------------------------------------------------------
# Локальная разработка (без контейнера API)
# ---------------------------------------------------------------------------

api: ## Локальный uvicorn с hot-reload (БД: make db)
	cd $(SERVER_DIR) && \
		DATABASE_URL="$(LOCAL_DATABASE_URL)" \
		uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend: ## Next.js dev-сервер на :3000
	pnpm --dir $(FRONTEND_DIR) install
	pnpm --dir $(FRONTEND_DIR) dev

# ---------------------------------------------------------------------------
# Проверки
# ---------------------------------------------------------------------------

test: ## Тесты backend (pytest)
	cd $(SERVER_DIR) && uv run pytest

lint-server: ## ruff + format-check + mypy
	cd $(SERVER_DIR) && uv run ruff check . \
		&& uv run ruff format --check . \
		&& uv run mypy .

lint-frontend: ## eslint + tsc
	pnpm --dir $(FRONTEND_DIR) lint
	pnpm --dir $(FRONTEND_DIR) typecheck

lint: lint-server lint-frontend ## Линтеры backend и frontend

fmt: ## Автоформат Python (ruff)
	cd $(SERVER_DIR) && uv run ruff check --fix . && uv run ruff format .

clean: ## Остановить контейнеры и удалить том Postgres
	$(COMPOSE) down -v
	@echo "Postgres volume removed. Next make up starts with an empty database."
