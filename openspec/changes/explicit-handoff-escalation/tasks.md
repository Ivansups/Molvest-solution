## 1. Детект хэндоффа в классификации

- [x] 1.1 `app/agent/state.py`: intent `handoff` в `Intent`, поле `escalation_reason` в `AgentState`; `mypy` зелёный
- [x] 1.2 `app/agent/nodes/classify.py`: `HANDOFF_ESCALATION_REASON`, регэкспы `_HANDOFF_EXCLUSION` / `_HANDOFF_REQUEST` / `_HANDOFF_DESIRE`, ветка `intent=handoff` с `escalated=true`; `classify` по-прежнему без вызова GigaChat

## 2. Маршрутизация графа

- [x] 2.1 `app/agent/graph.py`: `_after_classify` маршрутизирует `handoff` в `END` (мимо кэша/retrieve/generate); `ruff format` проходит

## 3. Причина эскалации сквозь персист

- [x] 3.1 `app/services/conversations.py`: `persist_turn(..., escalation_reason: str | None = None)`; `reason = escalation_reason or f"Низкая уверенность ретривала: {confidence:.2f}"`
- [x] 3.2 `app/services/agent.py`: `_initial_state` пишет `escalation_reason=""`; вызов `persist_turn` передаёт `escalation_reason=final.get("escalation_reason") or None`

## 4. Тесты

- [x] 4.1 `test_agent_graph.py::test_handoff_request_escalates_without_llm`: «Позовите оператора» → `intent=handoff`, `escalated=True`, retrieve/generate не вызваны (forbidden-retriever)
- [x] 4.2 `test_classify_handoff_rules`: позитивные формулировки дают `handoff` и `HANDOFF_ESCALATION_REASON`
- [x] 4.3 `test_classify_handoff_negatives`: «как позвать оператора в 1С», «можно ли позвать оператора» и т.п. остаются `support`
- [x] 4.4 `test_run_chat_turn_handoff_persists_reason`: статус `escalated`, один `Escalation` с причиной хэндоффа, гостю фраза с «оператор»
- [x] 4.5 Идемпотентность повторного хэндоффа — один `Escalation` (сценарий в спеках `conversation-records`)

## 5. Quality gate

- [x] 5.1 `cd server && uv run ruff check . && uv run ruff format --check . && uv run mypy .`
- [x] 5.2 `cd server && uv run pytest` (кроме pre-existing `test_bitrix_oauth.py::test_install_stores_token_pair` — live-вызов Bitrix из `.env`, падает без изменений и до этой работы)
- [x] 5.3 `cd server && uv run alembic check` (миграций нет)