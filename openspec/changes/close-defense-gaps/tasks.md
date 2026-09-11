## 1. Режим `operator_assist_mode`

- [x] 1.1 Расширить Literal до `draft | auto | agent` в `core/config.py`, `runtime_settings.py`, `schemas/settings.py`; дефолт `draft`; `.env.example`. Проверка: `GET /api/settings` после старта с env `draft` отдаёт `"draft"`
- [x] 1.2 `PUT /api/settings` принимает `agent`, отклоняет неизвестное значение 422. Проверка: тест readback `agent`; мусор → 422, override не меняется
- [x] 1.3 Подписи `/settings`: три пункта с понятным смыслом (не «черновик только по кнопке»); третье значение — режим `agent`. Проверка: select шлёт `draft`/`auto`/`agent`

## 2. Шлюз выдачи в `services/`

- [x] 2.1 Функция политики ответа (рядом с `run_chat_turn`): режим `agent` + есть `answer` → `open→escalated`, Escalation с причиной режима, `suggested_response=answer`, гостю фраза эскалации, без assistant с текстом модели. Роутеры не ветвят. Проверка: виджетный `POST /chat` при скоре ≥ порога в режиме `agent` — `escalated=true`, черновик заполнен, assistant-реплики с ответом нет
- [x] 2.2 режим `agent` + слабый скор: граф без generate, после commit `fill_escalation_draft`; если черновик уже есть — generate не звать. Проверка: статус `escalated`; generate_draft падает — статус жив, черновик пустой
- [x] 2.3 `draft` и `auto` без регрессии: первый уверенный ответ гостю; `draft` после эскалации — hold без generate на виджете; `auto` после эскалации — автоответ. Проверка: существующие тесты `test_agent_graph` / каналов зелёные
- [x] 2.4 Follow-up в режиме `agent` на `escalated`: persist user + `generate_draft`, гостю не слать. Проверка: вторая реплика обновляет `suggested_response`

## 3. `force_handoff` и кнопка

- [x] 3.1 `ChatRequest.force_handoff: bool = False`; в state графа. `handoff_detect` при флаге — хэндофф без OpenRouter/GigaChat. Проверка: флаг true — classify не звался; обычный вопрос — классификатор как сейчас
- [x] 3.2 Persist: одна Escalation с причиной явного запроса; повтор не плодит строку. Проверка: два `force_handoff` подряд — одна строка
- [x] 3.3 Виджет: кнопка «Позвать оператора» шлёт `force_handoff=true` и короткий текст; disabled на `resolved` и пока pending. Проверка: запрос содержит флаг; гость видит фразу эскалации, не черновик

## 4. PATCH документа

- [x] 4.1 `PATCH /api/documents/{id}`: `installation_id` в query, JSON `title` и/или `metadata`; пустое тело 422; чужая установка 404; чанки/status/`kb_version` не трогать. Проверка: смена title у INDEXED — чанки те же; повтор PATCH идемпотентен по смыслу
- [x] 4.2 `documentService.updateDocumentMetadata` зовёт PATCH, заглушку `unsupportedEndpoint` убрать; форма карточки живая. Проверка: category/description возвращаются в `metadata`

## 5. Подтверждение закрытия

- [x] 5.1 Alembic: `conversations.resolve_comment` (Text nullable), `resolve_confirmed_at` (timestamptz nullable), имена колонок явные. `uv run alembic check`
- [x] 5.2 `POST .../resolve`: обязателен `confirmed=true`, опциональный `comment`; иначе 422 и статус не меняется. Писать через `transition_status`; повтор на `resolved` — 200. Проверка: без confirmed — 422; два resolve — оба 200
- [x] 5.3 `GET /api/conversations/{id}` отдаёт новые поля; комментарий не уходит гостю и не в Bitrix/Redmine
- [x] 5.4 Модалка на `/operator` и `/chat/support`: да/нет + комментарий; да → resolve с `confirmed=true`; нет → запроса нет. Проверка: отмена оставляет `escalated`

## 6. Каналы

- [x] 6.1 `should_draft_followup` / `live_thread` / `ol_bot` / `openlines` / `redmine`: режим `agent` после эскалации или реплики оператора = ветка draft; первый `open` — `run_chat_turn` + шлюз. Адаптеры не копируют политику, смотрят `escalated`
- [x] 6.2 Тесты Bitrix и Redmine: режим `agent` + скор ≥ порога — тишина гостю, черновик есть; `auto` автоответ жив. Идемпотентный дубль события — дважды

## 7. UX виджета

- [x] 7.1 Индикатор ожидания: спиннер + текст + три точки (CSS). Проверка: текст «агент формирует ответ…» и точки, пока pending
- [x] 7.2 Источник: ~200 символов `chunk_text` сразу, полный текст по клику
- [x] 7.3 `guest_conversation_id` писать в sessionStorage и localStorage; читать session, иначе local; «Новый диалог» чистит оба; URL `?c=` не делать

## 8. Документация

- [x] 8.1 `docs/OPS.md`: env (имена), `/health`, БЗ включая PATCH, порог и три режима, ссылки на BITRIX.md / REDMINE.md. Не копировать DEV.md
- [x] 8.2 README: ссылка на OPS.md. ROADMAP §12: PATCH, кнопка хэндоффа, режимы, гайд админа — отметить закрытыми в рамках этого change

## 9. Quality gate

- [x] 9.1 `cd server && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest && uv run alembic check`
- [x] 9.2 `pnpm --dir frontend lint && pnpm --dir frontend typecheck`
- [x] 9.3 Регрессия: секреты не в логах/ответах; `draft`/`auto` поведение как до change, кроме новых путей
