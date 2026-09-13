## 1. Конфиг и клиент OpenRouter

- [x] 1.1 Добавить в `settings`/`.env.example` поля `OPENROUTER_API_KEY`,
  `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`, `OPENROUTER_TIMEOUT` (проверка:
  `ruff check` + чтение `.env.example`).
- [x] 1.2 В `app/core/openrouter_client.py` реализовать `RouterDecision`,
  `parse_router_decision` (fail-closed: код на первой строке, иначе
  `OpenRouterError`), `route()`, `is_configured()`; удалить
  `is_handoff_request` (проверка: `mypy` + тесты `route_intent_openrouter_*`).

## 2. Нода `router` в графе

- [x] 2.1 `git mv` `handoff_detect.py` → `router.py`; `route_intent`: ветка
  `force_handoff`, маршрутизация `text` гостя (не дамп Vision), фолбэк
  правила → GigaChat Lite → эскалация; константы `HANDOFF_ESCALATION_REASON`/
  `DETECTOR_FAILURE_REASON`; регулярки `_HANDOFF_RULES`/`_GREETING_ONLY`/
  `_AWAY_CHECK` терпимы к `. ! , ?` (проверка: тесты `test_route_intent_*`).
- [x] 2.2 В `app/agent/prompts.py` добавить `ROUTER_SYSTEM_PROMPT` и дефолтные
  шаблоны, `HANDOFF_SYSTEM_PROMPT` сохранить; расширить `state.Intent` до
  `empty|handoff|support|greeting|away|offtopic` (проверка: `mypy`).
- [x] 2.3 В `app/agent/graph.py` заменить ноду `handoff_detect` на `router` с
  условным переходом `_after_router`: `support` → `lookup_cache`, ответ/эскалация
  → `__end__` (проверка: graph-тесты `test_greeting_and_off_topic_end_at_router`).

## 3. Тесты

- [x] 3.1 Node-level тесты `route_intent`: SUPPORT/HANDOFF/GREETING/AWAY/
  OFFTopic, `text` вместо `query`, ошибка → правила → GigaChat → эскалация,
  пустой ключ, пустой query, fail-closed (проверка: `pytest
  tests/test_agent_graph.py -k route_intent`).
- [x] 3.2 Обновить graph/run_chat_turn/force_handoff тесты на сигнатуру
  `route()`; избавиться от `is_handoff_request` (проверка: `pytest
  tests/test_agent_graph.py` — 33 passed).
- [x] 3.3 Регресс-прогон всего backend (проверка: `pytest` — 93 passed; скiпы —
  только БД-зависимые без локального Postgres).

## 4. Качество и спека

- [x] 4.1 `uv run ruff check . && uv run ruff format --check . && uv run mypy .`
  — все чисто.
- [x] 4.2 Оформить openspec-артефакты (`proposal`/`specs`/`design`/`tasks`) и
  обновить Purpose `openspec/specs/agent-dialog-graph/spec.md` (проверка:
  `openspec validate` без ошибок).