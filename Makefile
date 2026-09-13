.DEFAULT_GOAL := help

COMPOSE       ?= docker compose
API_URL       ?= http://localhost:8000
WEB_URL       ?= http://localhost:3000
SERVER_DIR    := server
FRONTEND_DIR  := frontend
LOCAL_DATABASE_URL ?= postgresql+asyncpg://postgres:postgres@localhost:5432/molvest

.PHONY: help env setup \
	up down restart logs ps health health-api health-web \
	db migrate \
	api frontend \
	install install-server install-frontend \
	test test-server test-frontend \
	lint lint-server lint-frontend fmt \
	clean

help: ## Показать доступные команды
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make <target>\n\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  %-18s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@printf "\nQuick start:\n  make setup\n\n"

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

setup: up ## Полный первый запуск: .env, Docker (API + UI), проверка /health
	@echo ""
	@echo "API:     $(API_URL)/health"
	@echo "Docs:    $(API_URL)/docs"
	@echo "UI:      $(WEB_URL)"

up: env ## Собрать и поднять API + Postgres + UI, дождаться /health и :3000
	$(COMPOSE) up -d --build
	@$(MAKE) health

down: ## Остановить контейнеры (том БД не удаляется)
	$(COMPOSE) down

restart: ## Перезапустить контейнеры
	$(COMPOSE) restart

logs: ## Логи API, UI и Postgres (Ctrl+C — выход)
	$(COMPOSE) logs -f --tail=100

ps: ## Статус контейнеров
	$(COMPOSE) ps

db: env ## Поднять только Postgres (для локального uvicorn)
	$(COMPOSE) up -d db

migrate: env ## Повторно применить миграции в уже запущенном API
	$(COMPOSE) exec -T api alembic upgrade head

define wait-http
	echo "Waiting for $(1) at $(2) ..."; \
	i=0; \
	until curl -sf "$(2)" >/dev/null; do \
		i=$$((i + 1)); \
		if [ $$i -ge $(3) ]; then \
			echo "$(1) did not become ready in $(3)s. Try: make logs"; \
			exit 1; \
		fi; \
		sleep 1; \
	done
endef

health-api: ## Дождаться ответа API /health (до 180 с)
	@$(call wait-http,API,$(API_URL)/health,180)
	@curl -s "$(API_URL)/health" && echo

health-web: ## Дождаться UI :3000 и прокси /backend/health (до 240 с)
	@$(call wait-http,UI,$(WEB_URL),240)
	@$(call wait-http,UI-API,$(WEB_URL)/backend/health,30)
	@echo "UI ready: $(WEB_URL)"

health: health-api health-web ## Дождаться API /health и UI :3000

api: ## Локальный uvicorn с hot-reload (БД: make db). Сначала миграции.
	cd $(SERVER_DIR) && \
		export DATABASE_URL="$(LOCAL_DATABASE_URL)" && \
		uv run alembic upgrade head && \
		uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend: env ## Next.js в Docker на :3000 (не pnpm dev на хосте)
	$(COMPOSE) up -d --build web
	@$(MAKE) health-web

test-server: ## Тесты backend (pytest, без live LLM)
	cd $(SERVER_DIR) && uv run pytest -m "not live"

test-live: ## Живые smoke LLM (нужны ключи в .env)
	cd $(SERVER_DIR) && uv run pytest -m live

test-frontend: ## Тесты frontend (vitest)
	pnpm --dir $(FRONTEND_DIR) test

test: test-server test-frontend ## pytest + vitest

lint-server: ## ruff + format-check + mypy
	cd $(SERVER_DIR) && uv run ruff check . \
		&& uv run ruff format --check . \
		&& uv run mypy .

lint-frontend: ## eslint . + tsc (хост; UI при этом в Docker)
	pnpm --dir $(FRONTEND_DIR) lint
	pnpm --dir $(FRONTEND_DIR) typecheck

lint: lint-server lint-frontend ## Линтеры backend и frontend

fmt: ## Автоформат Python (ruff)
	cd $(SERVER_DIR) && uv run ruff check --fix . && uv run ruff format .

clean: ## Остановить контейнеры и удалить тома Postgres / Redis / UI
	$(COMPOSE) down -v
	@echo "Volumes removed. Next make up starts empty (DB + UI caches)."
