## Why

Эскалация сейчас срабатывает только при слабом скоре ретривала: явная просьба клиента
передать диалог человеку («позовите оператора», «нужен человек») уходит в обычный
RAG-ответ вместо передачи оператору. Клиент вынужден повторять просьбу, а операторы
теряют тикеты с явным сигналом о неудовлетворённости. Правила-регэкспы для детекта
хэндоффа хрупки (неполный словарь формулировок, ложные срабатывания на вопросах
«как позвать оператора»), чистый LLM-классификатор на лёгкой модели OpenRouter
решает проблему точнее и дешевле.

## What Changes

- Новый узел графа `handoff_detect` после `classify`: вызывает лёгкую LLM
  (OpenRouter, meta-llama/llama-3.1-8b-instruct) для классификации запроса —
  `YES` (просьба передать человеку) → эскалация сразу, без retrieve/generate;
  `NO` → обычный путь support. Пустой ключ OpenRouter — детект пропускается.
- Классификатор `OpenRouterClassifier` в `core/openrouter_client.py`: строгий
  YES/NO промпт, timeout 10 сек, `temperature=0`. Синглтон с параметрами из env;
  для тестов — мок через `MagicMock(spec=OpenRouterClassifier)`.
- `classify` остаётся без LLM и без правил хэндоффа: только `empty`/`support`
  (как было до регэкспов). Нода `handoff_detect` отвечает за детект хэндоффа.
- Сбой классификатора (сеть/HTTP/неразборчивый ответ) — фолбэк в `support`,
  чат не роняется.
- В графе `_after_classify`: `empty` → `__end__`, `support` → `handoff_detect`;
  `_after_handoff_detect`: `handoff` → `__end__`, `support` → `lookup_cache`.
- Прокинуть `escalation_reason` из состояния графа в персист: при хэндоффе тикет
  получает причину «Явный запрос передачи оператору» (константа `HANDOFF_ESCALATION_REASON`
  в `handoff_detect.py`).
- Переход в `escalated` по-прежнему только через центральный сервис статуса; гость
  получает штатную фразу `GUEST_ESCALATION_TEXT`; тикет виден в консоли оператора.
- Идемпотентность сохраняется: повтор просьбы не создаёт второй `Escalation`.

## Capabilities

### New Capabilities

- `handoff-classification`: LLM-классификатор хэндоффа на OpenRouter: промпт,
  модель, таймаут, фолбэк при сбое, отключение при пустом ключе. Нода
  `handoff_detect` в графе, вызывающая классификатор.

### Modified Capabilities

- `agent-dialog-graph`: после `classify` добавлена нода `handoff_detect`,
  вызывающая LLM-классификатор. Маршрут `support` → `handoff_detect` →
  `lookup_cache` или `__end__`. Intent `handoff` эскалирует до retrieve/generate.
- `conversation-records`: причина эскалации в `Escalation.reason` отражает источник —
  низкий скор ретривала или явная просьба клиента о передаче оператору.

## Impact

- `server/app/core/config.py` — настройки OpenRouter (`openrouter_api_key`,
  `openrouter_base_url`, `openrouter_model`, `openrouter_timeout`).
- `server/app/core/openrouter_client.py` (новый) — `OpenRouterClassifier`,
  `OpenRouterError`, `get_openrouter_classifier()`.
- `server/app/agent/nodes/handoff_detect.py` (новый) — нода `handoff_detect`,
  `HANDOFF_ESCALATION_REASON`.
- `server/app/agent/nodes/classify.py` — регэкспы удалены; только `empty`/`support`.
- `server/app/agent/graph.py` — нода `handoff_detect`, параметр `handoff_classifier`,
  маршрутизация `_after_classify`/`_after_handoff_detect`.
- `server/app/services/agent.py`, `server/app/services/conversations.py` — проброс
  и запись `escalation_reason`.
- Тесты: граф-эскалация без вызова модели, YES/NO/сбой/не настроен/пустой запрос,
  persist причины и идемпотентность.
- Миграции БД не требуются; контракт `POST /chat` не меняется.
