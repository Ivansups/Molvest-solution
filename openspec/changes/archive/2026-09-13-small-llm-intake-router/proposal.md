## Why

Приветствие, «ты тут?» и явный оффтоп сейчас прогоняются через весь граф:
RAG-ретривал, эмбеддинги и `generate` GigaChat на трафик, который не должен
нагружать тяжёлую модель. GigaChat остаётся единственным генератором ответов
по 1С, но отсечение нерелевантного трафика — это другая, более дешёвая
задача: её решает лёгкая LLM (OpenRouter) на intake-этапе, до кэша и RAG.
Заодно детект хэндоффа переезжает с «да/нет» на маршрутизацию с кодами —
один вызов вместо «а не хэндофф ли это», плюс явные короткие ответы.

## What Changes

- **Нода `router` вместо `handoff_detect`** в графе: после `classify`, до
  кэша и RAG. Возвращает маршрут `support | handoff | greeting | away |
  offtopic` и короткий ответ для коротких маршрутов. **BREAKING (внутреннее):**
  узел графа переименован, метод `OpenRouterClassifier.is_handoff_request()`
  удалён.
- **`OpenRouterClassifier.route()`**: строгий формат ответа малой модели —
  код на первой строке, короткий ответ ниже (`SUPPORT`/`HANDOFF`/
  `GREETING`/`AWAY_CHECK`/`OFFTOPIC`). Неразборчивый ответ и пустой контент —
  `OpenRouterError`, никогда не трактуются как `support`.
- **`greeting`/`away`/`offtopic`** отвечают в роутере: `intent`, короткий
  `answer` (из малой модели или запасной шаблон), `confidence=1.0`,
  `escalated=false`, граф заканчивается без retrieve/generate. Не пишутся в
  кэш ответа. **Меняет старое требование**: приветствие/оффтоп больше не
  всегда доходят до GigaChat.
- **`handoff`** — как раньше: `escalated=true`, `escalation_reason` из
  константы, граф заканчивается.
- **`support`** — продолжает путь кэш → retrieve → generate на GigaChat.
- **Фолбэк без OpenRouter** (пустой ключ или сбой): правила по regex для
  коротких «чистых» реплик (приветствие/проверка связи/явный хэндофф), затем
  GigaChat-2 (Lite) YES/NO для хэндоффа. Сбой всех путей — эскалация с
  причиной сбоя детекта, не ответ из базы.
- **Роутится текст гостя** (`text`), а не дамп Vision (`query`); `force_handoff`
  срезает всё до вызова классификатора.
- Правила фолбэка терпимы к хвостовой пунктуации `.`, `!`, `,`, `?`.

## Capabilities

### New Capabilities

- (нет)

### Modified Capabilities

- `agent-dialog-graph`: нода `router` с intents `support | handoff |
  greeting | away | offtopic`; приветствие/проверка связи/оффтоп отвечают
  коротким шаблоном без retrieve/generate; фолбэк правила → GigaChat Lite →
  эскалация; `support` по-прежнему идёт через кэш/retrieve/generate.

## Impact

- `server/app/agent/nodes/`: `router.py` (новый, замена `handoff_detect.py`);
  `classify.py` — docstring.
- `server/app/core/openrouter_client.py`: `route()`, `RouterDecision`,
  `parse_router_decision`, `is_configured()`; удалён `is_handoff_request`.
- `server/app/agent/prompts.py`: `ROUTER_SYSTEM_PROMPT`, запасные шаблоны
  `DEFAULT_GREETING_REPLY`/`DEFAULT_AWAY_REPLY`/`DEFAULT_OFFTOPIC_REPLY`;
  `HANDOFF_SYSTEM_PROMPT` сохранён для фолбэка GigaChat.
- `server/app/agent/state.py`: `Intent` расширен (`greeting`, `away`,
  `offtopic`, `empty`, `handoff`, `support`).
- `server/app/agent/graph.py`: нода `router`, условные переходы `_after_router`.
- `.env.example`: `OPENROUTER_API_KEY`/`OPENROUTER_BASE_URL`/`OPENROUTER_MODEL`/
  `OPENROUTER_TIMEOUT`.
- Тесты `server/tests/test_agent_graph.py`: блок route_intent + обновлённые
  graph/force_handoff/run_chat_turn тесты.

Вне scope: генерация ответов по 1С на малой модели, эмбеддинги, обучение на
кейсах, CSAT, изменения каналов (Bitrix/Redmine/email) и фронтенда.