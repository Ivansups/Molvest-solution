## 1. Общий handoff канальной эскалации

- [x] 1.1 Вынести helper после commit эскалации: `generate_draft` → запись `suggested_response` отдельным commit; ошибка generate не откатывает статус. Виджетный `POST /chat` не вызывать. Проверить юнит-тестом: эскалация есть, черновик записан; generate падает — статус `escalated`, `suggested_response` пустой

## 2. REST Bitrix: файл по id и заметка оператору

- [x] 2.1 `Bitrix24RestClient`: скачивание вложения по file id (`disk.file.get` / download) через OAuth; хост по-прежнему только домен портала. Юнит-тест с `httpx.MockTransport`, токен не в логах
- [x] 2.2 Метод операторской заметки (не `imbot.message.add` гостю и не `imconnector.send.messages`). Спайк на `b24-adkm07.bitrix24.ru`: зафиксировать метод в design.md. Пока метод неизвестен — клиент принимает dialog_id + text, ошибка REST = warning. Тест: гостевой send не вызывается

## 3. Эскалация и скриншот на боте и коннекторе

- [x] 3.1 `ol_bot.py`: при `escalated=True` после commit вызвать helper 1.1, затем заметку 2.2; `imbot.message.add` гостю не звать. Тест: ниже порога — тишина клиенту, `suggested_response` заполнен
- [x] 3.2 `openlines.py`: то же для коннектора (`imconnector.send.messages` гостю не звать). Регрессия `test_bitrix_channel.py`: автоответ выше порога жив
- [x] 3.3 `_fetch_image` бота и коннектора: url как сейчас, иначе file id через 2.1; нет текста + есть картинка → не welcome/empty. Сбой скачивания — warning, ход текстом, не 5xx. Тесты: url, file id, сбой

## 4. Сценарий 2 на событиях портала

- [x] 4.1 В `ol_bot` / `openlines`: если диалог `escalated` или в ленте есть `role=operator`, и режим `draft` — persist user + `generate_draft` + `suggested_response` + заметка, без гостевого send. Тест: follow-up после эскалации; follow-up после сообщения оператора
- [x] 4.2 Тот же признак, режим `auto` — `run_chat_turn` и гостевой send как в сценарии 1. Тест смены режима через `update_effective_settings` без рестарта
- [x] 4.3 Регрессия: `POST /webhook/bitrix` (внутренний токен, `live_thread`) и коннекторный `/openlines` выше порога не сломаны. Оператор по-прежнему без графа

## 5. Redmine HelpDesk

- [x] 5.1 `core/config.py` + `.env.example`: блок `REDMINE_*` / IMAP/SMTP без секретов. Пустой IMAP допустим
- [x] 5.2 Схемы события и `POST /webhook/redmine` (внутренний токен, 403 без записи, 422 на кривой формат). Роутер в `main.py`. Тест OpenAPI + 403/422
- [x] 5.3 Сервис: `channel="redmine"`, маппинг `ticket_id`, дубль по `message_id`, оператор без графа, гость → `run_chat_turn`; выше порога исходящее после commit; ниже — helper 1.1, в тикет гостю ничего. Тесты маппинга, дубля (дважды), эскалации, автоответа
- [x] 5.4 Исходящий клиент (Redmine note и/или SMTP) после commit, секреты не в логах. Mock в тестах 5.3

## 6. IMAP (опционально)

- [x] 6.1 Если `REDMINE_IMAP_*` заданы — поллер зовёт сервис 5.3; пустые env — поллера нет, вебхук жив. Тест: без IMAP API стартует; с IMAP одно письмо → один вызов сервиса (мок)

## 7. Документация

- [x] 7.1 `docs/BITRIX.md` + README: эскалация = тишина гостю + черновик в консоли + заметка; сценарий 2 после оператора; скриншот; для демо Q&A по-прежнему `auto`
- [x] 7.2 `docs/ROADMAP.md` §§12 и 15: убрать «канала Bitrix нет»; честно описать Redmine (вебхук обязателен, IMAP опционален)
- [x] 7.3 README: таблица Redmine env и `POST /webhook/redmine`

## 8. Quality gate

- [x] 8.1 Тесты handoff, live-portal draft/auto, screenshot, redmine + регрессия бота/коннектора/`/webhook/bitrix`. Дубль идемпотентных операций вызвать дважды. Секреты не в ответах и логах
- [ ] 8.2 `cd server && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest && uv run alembic check`

## 9. Ручная проверка портала

- [ ] 9.1 На `b24-adkm07.bitrix24.ru`: слабый вопрос → гость молчание, черновик в `/operator`, заметка оператору если метод из 2.2 подтверждён
- [ ] 9.2 После эскалации в `draft` следующая реплика гостя не отвечает ботом, черновик обновляется; в `auto` — ответ в том же окне
- [ ] 9.3 Скриншот PNG в онлайн-чате проходит vision (или честный fallback, если портал не отдаёт file id). Расхождения формата — в design.md
