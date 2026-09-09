## 1. OpenRouter-адаптер и нода `handoff_detect`

- [x] 1.1 `app/core/config.py`: настройки `openrouter_api_key` (по умолчанию `""`), `openrouter_base_url`, `openrouter_model`, `openrouter_timeout`
- [x] 1.2 `app/core/openrouter_client.py`: `OpenRouterClassifier` (`is_handoff_request`, `_classify`, `is_configured`), `OpenRouterError`, `get_openrouter_classifier()`; синквер `httpx.AsyncClient`, `max_tokens=5`, `temperature=0`
- [x] 1.3 `app/agent/nodes/handoff_detect.py`: нода `handoff_detect(state, *, classifier)`; `HANDOFF_ESCALATION_REASON`; фолбэк в `{}` при `OpenRouterError`; пустой query/не настроен → пропуск
- [x] 1.4 `app/agent/nodes/classify.py`: регэкспы удалены, только `empty`/`support`, без вызова GigaChat
- [x] 1.5 `.env.example`: блок OpenRouter с пояснением «пустой ключ = детект отключён»

## 2. Маршрутизация графа

- [x] 2.1 `app/agent/graph.py`: нода `handoff_detect`; `build_graph(..., handoff_classifier=None)` (дефолт — `get_openrouter_classifier()`); `_after_classify`: empty → `__end__`, support → `handoff_detect`; `_after_handoff_detect`: handoff → `__end__`, support → `lookup_cache`

## 3. Причина эскалации сквозь персист

- [x] 3.1 `app/services/conversations.py`: `persist_turn(..., escalation_reason: str | None = None)`; `reason = escalation_reason or f"Низкая уверенность ретривала: {confidence:.2f}"`
- [x] 3.2 `app/services/agent.py`: вызов `persist_turn` передаёт `escalation_reason=final.get("escalation_reason") or None`

## 4. Тесты

- [x] 4.1 `test_agent_graph.py::test_handoff_detect_yes_escalates`: классификатор YES → `intent=handoff`, `escalated=True`, `HANDOFF_ESCALATION_REASON` (нода)
- [x] 4.2 `test_agent_graph.py::test_handoff_detect_no_keeps_support`: вопросы «как … оператора» c NO остаются `support` (нода)
- [x] 4.3 `test_agent_graph.py::test_handoff_detect_error_falls_back_to_support`: сбой → фолбэк `{}`
- [x] 4.4 `test_agent_graph.py::test_handoff_detect_not_configured_skips` / `test_handoff_detect_empty_query_skips`: пустой ключ и пустой query не трогают классификатор
- [x] 4.5 `test_agent_graph.py::test_handoff_request_escalates_without_llm`: граф с YES-классификатором — retrieve/generate не вызваны
- [x] 4.6 `test_agent_graph.py::test_handoff_no_goes_to_support` / `test_handoff_error_falls_back_to_support` / `test_handoff_classifier_disabled_skips_detection`: граф-пути NO / сбой / отключен
- [x] 4.7 `test_agent_graph.py::test_run_chat_turn_handoff_persists_reason`: статус `escalated`, один `Escalation` с причиной хэндоффа, гостю фраза с «оператор»
- [x] 4.8 Идемпотентность повторного хэндоффа — один `Escalation` (сценарий в спеках `conversation-records`)

## 5. Quality gate

- [x] 5.1 `cd server && uv run ruff check . && uv run ruff format --check . && uv run mypy .`
- [x] 5.2 `cd server && uv run pytest` (кроме pre-existing `test_bitrix_oauth.py::test_install_stores_token_pair` — live-вызов Bitrix из `.env`, падает без изменений и до этой работы)
- [x] 5.3 `cd server && uv run alembic check` (миграций нет)