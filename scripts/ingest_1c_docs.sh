#!/usr/bin/env bash
# Ручная загрузка публичной документации 1С в базу знаний.
#
# Compose / Dockerfile / entrypoint этот скрипт НЕ вызывают.
# Полный ITS (its.1c.ru) — по подписке; сюда только открытые PDF/HTML
# с v8.1c.ru, solutions.1c.ru и статьи Википедии (CC BY-SA).
#
# Запуск (стек уже поднят: make up):
#   ./scripts/ingest_1c_docs.sh
#
# Переменные:
#   INSTALLATION_ID  — id установки консоли
#                      (дефолт 7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11)
#   CACHE_DIR        — куда класть скачанные файлы
#                      (дефолт server/data/1c-docs-cache)
#   FORCE_DOWNLOAD=1 — качать заново, даже если файл уже есть
#   INGEST_LOCAL=1   — uv на хосте вместо docker compose exec api
#   DATABASE_URL     — только для INGEST_LOCAL; хост db: в URL
#                      заменяется на localhost
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CACHE_DIR="${CACHE_DIR:-$ROOT/server/data/1c-docs-cache}"
INSTALLATION_ID="${INSTALLATION_ID:-7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11}"
UA="Molvest-1C-KB-ingest/1.0 (manual knowledge-base load)"
MANIFEST="$CACHE_DIR/manifest.tsv"

mkdir -p "$CACHE_DIR"
: >"$MANIFEST"

download() {
  local url="$1"
  local dest="$2"
  local title="$3"
  if [[ -s "$dest" && "${FORCE_DOWNLOAD:-}" != 1 ]]; then
    printf '%s\t%s\t%s\n' "$(basename "$dest")" "$title" "$url" >>"$MANIFEST"
    echo "уже скачан $(basename "$dest")"
    return
  fi
  echo "качаю $(basename "$dest")"
  curl -fsSL --retry 3 --retry-delay 2 -A "$UA" -o "$dest.part" "$url"
  mv "$dest.part" "$dest"
  printf '%s\t%s\t%s\n' "$(basename "$dest")" "$title" "$url" >>"$MANIFEST"
}

# Официальные открытые PDF (без логина ITS).
download \
  "https://v8.1c.ru/upload/static/instrukciya-po-ehkspluatacii-v8.pdf" \
  "$CACHE_DIR/1c-enterprise-83-user-guide.pdf" \
  "1С:Предприятие 8.3. Руководство пользователя"

download \
  "https://v8.1c.ru/upload/static/instrukciya-po-ustanovke-i-zapusku-v8.pdf" \
  "$CACHE_DIR/1c-enterprise-install-platform.pdf" \
  "1С:Предприятие 8. Установка и запуск платформы"

download \
  "https://v8.1c.ru/upload/static/instrukciya-po-ustanovke-i-zapusku.pdf" \
  "$CACHE_DIR/1c-enterprise-install-product.pdf" \
  "1С:Предприятие 8. Установка и запуск основной поставки"

download \
  "https://v8.1c.ru/upload/static/instrukciya-po-ehkspluatacii-produkta-bau.pdf" \
  "$CACHE_DIR/1c-accounting-autonomous-institution.pdf" \
  "1С:Бухгалтерия автономного учреждения 8. Инструкция"

download \
  "https://v8.1c.ru/upload/static/delovye-prilozheniya-na-desktope-i-v-oblake-v-brauzere-i-na-iphone.pdf" \
  "$CACHE_DIR/1c-platform-desktop-cloud-browser.pdf" \
  "Платформа 1С:Предприятие: десктоп, облако, браузер"

download \
  "https://v8.1c.ru/upload/static/new-doc8-3_0_12.pdf" \
  "$CACHE_DIR/1c-document-flow-3-0-12.pdf" \
  "1С:Документооборот 3.0.12. Что нового"

download \
  "https://solutions.1c.ru/upload/reestr/48f/4crh3rmyn6mjrsk1kkqe33vugiwsvh29/Instruktsiya-po-ekspluatatsii-_-1S_Obshchepit.pdf" \
  "$CACHE_DIR/1c-catering-user-guide.pdf" \
  "1С:Общепит. Руководство пользователя"

# Открытые HTML-страницы v8.1c.ru.
download \
  "https://v8.1c.ru/tekhnologii/overview/" \
  "$CACHE_DIR/1c-platform-overview.html" \
  "Обзор платформы 1С:Предприятие 8"

download \
  "https://v8.1c.ru/tekhnologii/systemnye-trebovaniya-1s-predpriyatiya-8/" \
  "$CACHE_DIR/1c-system-requirements.html" \
  "Системные требования 1С:Предприятие 8"

download \
  "https://v8.1c.ru/tekhnologii/standartnye-biblioteki/" \
  "$CACHE_DIR/1c-standard-libraries.html" \
  "Стандартные библиотеки 1С:Предприятие"

# Википедия, CC BY-SA 4.0. Не ITS.
download \
  "https://ru.wikipedia.org/api/rest_v1/page/html/1%D0%A1:%D0%9F%D1%80%D0%B5%D0%B4%D0%BF%D1%80%D0%B8%D1%8F%D1%82%D0%B8%D0%B5" \
  "$CACHE_DIR/wikipedia-1c-enterprise.html" \
  "Википедия: 1С:Предприятие (CC BY-SA)"

download \
  "https://ru.wikipedia.org/api/rest_v1/page/html/1%D0%A1:%D0%91%D1%83%D1%85%D0%B3%D0%B0%D0%BB%D1%82%D0%B5%D1%80%D0%B8%D1%8F" \
  "$CACHE_DIR/wikipedia-1c-accounting.html" \
  "Википедия: 1С:Бухгалтерия (CC BY-SA)"

echo "индексация installation_id=$INSTALLATION_ID"

if [[ "${INGEST_LOCAL:-}" == 1 ]]; then
  cd "$ROOT/server"
  db_url="${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:5432/molvest}"
  if [[ "$db_url" == *"@db:"* ]]; then
    db_url="${db_url//@db:/@localhost:}"
  fi
  DATABASE_URL="$db_url" uv run python -m app.cli.ingest_1c_docs \
    --dir "$CACHE_DIR" \
    --installation-id "$INSTALLATION_ID"
  exit $?
fi

cd "$ROOT"
if ! docker compose exec -T api python -c "import app" >/dev/null 2>&1; then
  echo "контейнер api не запущен. Сначала: make up" >&2
  echo "либо INGEST_LOCAL=1 (uv на хосте, Postgres на localhost)" >&2
  exit 1
fi

docker compose exec -T api python -m app.cli.ingest_1c_docs \
  --dir /app/data/1c-docs-cache \
  --installation-id "$INSTALLATION_ID"
