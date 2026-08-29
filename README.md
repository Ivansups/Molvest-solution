# Molvest-solution
Хакатоновская задачка от компании "Молвест"

## Запуск

```bash
cp .env.example .env   # заполнить GIGACHAT_API_KEY и остальные переменные
docker compose up -d --build
```

- API: http://localhost:8000 (`/health`, `/docs`)
- Postgres (pgvector): localhost:5432
- Frontend (Next.js): `pnpm --dir frontend dev` — http://localhost:3000

Применить миграции (после того как появятся модели, см. `docs/ROADMAP.md`):

```bash
docker compose exec api alembic upgrade head
```

## Локальная разработка backend (без Docker)

```bash
cd server
uv sync
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy .
```

См. `AGENTS.md` — структура проекта и правила разработки, `docs/ROADMAP.md` —
план по этапам.
