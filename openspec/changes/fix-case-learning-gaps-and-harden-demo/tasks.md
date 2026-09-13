## 1. Фикс fail-closed в case learning

- [x] 1.1 Изменить `_ingest_case` в `server/app/services/case_learning.py`,
      чтобы она возвращала `bool` (`True` — документ создан и закоммичен,
      `False` — `IngestionError`, документ удалён и откачен)
- [x] 1.2 В `evaluate_and_ingest` вызывать `_mark_ingested` после успешного
      `_ingest_case` только когда она вернула `True`
- [x] 1.3 Добавить в `server/tests/test_case_learning.py` тест: при
      `IngestionError` от `index_document` (замокать) `case_ingested_at`
      остаётся `None`, а повторный вызов `evaluate_and_ingest` для того же
      диалога снова доходит до попытки индексации
- [x] 1.4 Прогнать `pytest server/tests/test_case_learning.py` локально или
      через CI, убедиться в зелёном прогоне

## 2. Точность документации: RAG-порог и case learning

- [x] 2.1 В `docs/SCENARIOS.md` (Сценарий 1) заменить формулировку
      "уверенность модели" на "similarity-скор поиска (топ-1 чанк)", убрать
      намёк на самооценку LLM
- [x] 2.2 В `README.md` синхронизировать формулировку порога с исправленной
      в `docs/SCENARIOS.md`
- [x] 2.3 В `docs/SCENARIOS.md` (Сценарий 4, автоинжест кейсов) явно
      прописать, что источник — автоответ ассистента без эскалации, а не
      решение/правка оператора

## 3. Наблюдаемость: OpenRouter no-op

- [x] 3.1 Добавить в `docs/OPS.md` раздел/заметку: при пустом
      `OPENROUTER_API_KEY` case learning и handoff-detect молча
      деградируют (пропуск/фолбэк на GigaChat-2), проверяется по INFO-логу
      `case learning: OpenRouter не настроен`

## 4. Чек-лист хардненинга для демо-хоста

- [x] 4.1 Добавить в `docs/OPS.md` раздел "Перед публичным демо": задать
      непустой `INTERNAL_SERVICE_TOKEN`, заменить дефолтные
      `POSTGRES_USER`/`POSTGRES_PASSWORD`, не публиковать порт Postgres
      наружу
- [x] 4.2 Добавить комментарии в `.env.example` рядом с
      `POSTGRES_PASSWORD=postgres` и `INTERNAL_SERVICE_TOKEN=`, что это
      dev-only дефолты, обязательные к замене вне локальной разработки
- [x] 4.3 В `docs/BITRIX.md` явно отметить, что `POST
      /webhook/bitrix/install` не проверяет подпись/токен запроса и
      полагается на приватность handler-URL (ngrok) как единственный барьер

## 5. Честность CI-покрытия

- [x] 5.1 Добавить в `docs/TESTS.md` раздел "Известные пробелы": моки
      GigaChat/OpenRouter/Vision в CI, отсутствие прогона Redis,
      Alembic-миграций сквозным образом и живого Vision; отметить, что
      happy path case learning проверялся вручную против живых сервисов

## 6. Мультипровайдерность как дизайн-решение

- [x] 6.1 В `README.md` и/или `docs/ROADMAP.md` добавить одну строку: ТЗ не
      требует единственного вендора LLM; OpenRouter используется осознанно
      для быстрых шагов классификации (handoff-detect, GOOD/BAD кейса)

## 7. Финализация

- [x] 7.1 Прогнать `ruff check . && ruff format --check . && mypy .` в
      `server/` после правок кода
- [x] 7.2 Свести все изменения в один коммит/PR по списку Impact из
      `proposal.md`
