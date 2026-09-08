## Context

Сценарий 1 в Bitrix уже живой: `POST /webhook/bitrix/bot` → `run_chat_turn`
→ `imbot.message.add`. Коннектор (`openlines`) и импровизированный
`POST /webhook/bitrix` (`live_thread`, внутренний токен) рядом.

Дыры относительно ТЗ (`Молвест.xlsx`, `docs/SCENARIOS.md`):

1. Ниже порога клиенту тишина — ок; оператор не получает черновик.
   `persist_turn` при эскалации оставляет `suggested_response` пустым
   (консоль: кнопка «Сгенерировать»). В Bitrix заметки оператору нет.
2. Сценарий 2 на портале: после `escalated` в `draft` гость идёт в
   `persist_guest_hold` без generate. `live_thread` уже умеет черновик, но
   только на внутреннем вебхуке.
3. Скриншот: `ol_bot` / `openlines` берут только `FILES[].url`. У события
   часто file id / disk, без прямого URL — vision не вызывается.
4. Redmine/почты в коде нет. Маппинг — тот же `ChannelThread`.

Инварианты: статус только через transition-сервис; внешний REST после
commit; секреты в env; ядро агента не знает канал.

## Goals / Non-Goals

**Goals:**

- Эскалация Bitrix/Redmine: тишина гостю, черновик в `suggested_response`,
  операторская заметка в том же диалоге Bitrix (best-effort).
- Сценарий 2 на событиях бота/линии: `draft` → черновик, `auto` → ответ
  гостю; импровизированный `/webhook/bitrix` остаётся.
- Вложение Bitrix (url или file id) → `image_base64` → существующий vision.
- Redmine: входящий тикет/письмо → `run_chat_turn`, исходящий ответ в тикет.

**Non-Goals:**

- Подстановка текста в поле ввода оператора Bitrix (REST этого не даёт).
- Обучение на успешных кейсах (сценарий 4).
- Удаление `/webhook/bitrix` и кастомного коннектора.
- Смена дефолта `OPERATOR_ASSIST_MODE` (остаётся `draft`).
- Виджет `POST /chat`: первая эскалация по-прежнему без generate.

## Decisions

### D1. Черновик при эскалации канала — после commit, через `generate_draft`

Виджет не трогаем: `POST /chat` ниже порога по-прежнему не вызывает
generate (экономия токена, текущий `operator-assist`).

Канальный ход (`bitrix_ol_bot` / `bitrix_openlines` / `redmine`): после
commit эскалации вызываем уже существующий `generate_draft` (как
`live_thread` в draft). Результат пишем в `suggested_response` отдельным
commit. Затем — операторская заметка в Bitrix, вне транзакции.

Альтернатива «generate внутри графа при escalate» отклонена: ломает
виджет и смешивает гостевой ответ с черновиком. Альтернатива «очередь /
фон» отклонена: YAGNI, `live_thread` уже считает черновик в том же запросе.

### D2. Заметка оператору в Bitrix — не `imbot.message.add` гостю

Гостю по эскалации по-прежнему ничего не шлём (`imbot.message.add` /
`imconnector.send.messages` не вызываются).

Оператору: отдельный REST после commit черновика. Метод на тестовом
портале — `im.notify` на `BITRIX_APP_USER_ID` (личное уведомление,
гость онлайн-чата не видит). Не `imbot.message.add` и не
`imconnector.send.messages`. Ошибка REST = warning + эскалация в БД
уже есть; консоль с `suggested_response` — запасной канал.

Альтернатива «только консоль» слабее ТЗ («через тот же канал»), поэтому
заметку делаем, но не блокируем эскалацию.

### D3. Сценарий 2 — те же вебхуки бота/линии, не четвёртый URL

Признак «уже у оператора»: `Conversation.status == escalated` **или** в
ленте есть `role=operator`. Тогда:

- `draft` → как `live_thread._process_draft`: persist user, `generate_draft`,
  `suggested_response`, заметка оператору, гостю ничего.
- `auto` → текущий `run_chat_turn` (ответ гостю при высоком скоре).

Первое сообщение в `open` — сценарий 1, без изменений ветки графа.

Импровизированный `POST /webhook/bitrix` не удаляем: тесты и демо без
портала. Общую логику «гость после оператора» не выносим в третий сервис,
пока копипаста меньше ~40 строк; если повторится в Redmine — общий helper
рядом с `draft.py`.

### D4. Скриншот — url, иначе file id через REST disk

Порядок: прямой `url`/`link` (хост = домен портала, как сейчас, анти-SSRF);
иначе `id` / `fileId` → `disk.file.get` / скачивание через OAuth REST;
base64 в `ChatRequest.image_base64`. Картинка без текста — граф уже умеет
vision. Недоступный файл: warning, ход как текст, вебхук не 5xx.

Альтернатива «только url» — текущая дыра. Retry/очередь — вне scope.

### D5. Redmine — тестовый вебхук + опциональный IMAP

Контракт, который тестируем: `POST /webhook/redmine` (внутренний токен,
как `/webhook/bitrix`): `ticket_id`, `message_id`, `sender`, `text`,
опционально вложение. `ChannelThread(channel="redmine", thread_id=ticket_id)`.
Исходящее: Redmine REST note / SMTP, после commit. Эскалация — тот же
handoff (черновик в консоли; в тикет гостю ничего).

IMAP: если заданы `REDMINE_IMAP_*`, фоновый цикл читает ящик и зовёт тот
же сервис. Без IMAP вебхук достаточен для защиты (как импровизация Bitrix).

Альтернатива «только IMAP» отклонена: хрупко в pytest. Альтернатива
«полный Redmine UI» — вне хакатона.

### D6. Конфиг и секреты

Новые env только `REDMINE_*` / IMAP/SMTP в `core/config.py` и
`.env.example`, без реальных значений. Bitrix-токены не дублируем.
В `/settings` не выносим.

## Risks / Trade-offs

- [Вебхук Bitrix упрётся в таймаут из-за generate_draft] → тот же риск, что
  у `live_thread`; при ошибке generate эскалация уже закоммичена, черновик
  пустой, оператор жмёт «Сгенерировать».
- [Метод операторской заметки на портале другой] → либеральный клиент +
  спайк 1.x; консоль — запасной канал ТЗ.
- [В `draft` после первой эскалации бот молчит гостю] → это сценарий 2,
  не регрессия онлайн-чата; для демо «написал → бот ответил» по-прежнему
  `OPERATOR_ASSIST_MODE=auto` (`docs/BITRIX.md`).
- [IMAP недоступен на защите] → вебхук Redmine.
- [File id требует scope `disk`] → уже в правах приложения.

## Migration Plan

1. Код и тесты; новой таблицы нет (`suggested_response` и `ChannelThread`
   уже есть).
2. `docs/BITRIX.md` — эскалация с черновиком и сценарий 2; README — Redmine
   env; `docs/ROADMAP.md` §§12 и 15 — убрать «канала Bitrix нет», оставить
   честный статус Redmine/IMAP.
3. Откат: флаги/ветки в `ol_bot`/`openlines` и `include_router` Redmine;
   живые диалоги не мигрируем.

## Open Questions

- Точный REST для операторской заметки Open Lines — спайк на
  `b24-adkm07.bitrix24.ru` до закрытия задачи handoff.
- Redmine: REST notes vs SMTP — выбрать по тому, что даст заказчик к
  защите; вебхук обязателен в любом случае.
