## Purpose

Сценарий 1 ТЗ рядом с кастомным коннектором: сотрудник пишет как клиент в штатном окне Bitrix (онлайн-чат открытой линии / диалог с ботом), агент отвечает в том же диалоге через `imbot`. Коннектор не удаляется и не подменяет этот путь.

## ADDED Requirements

### Requirement: Входящий webhook бота принимает ONIMBOTMESSAGEADD

The system SHALL expose `POST /webhook/bitrix/bot` as the Bitrix `EVENT_MESSAGE_ADD` handler. Each accepted event SHALL carry a dialog id (`DIALOG_ID`), a channel message id, an author id, optional text, and optional file or image attachment references. The system SHALL authenticate with the Bitrix application token (same fail-closed rule as the connector webhook) and SHALL reject events without a valid token with HTTP 403 and without changing any state. Join/welcome events without a guest question SHALL NOT run the agent graph.

#### Scenario: Первое сообщение клиента в онлайн-чате создаёт диалог

- **WHEN** a guest `ONIMBOTMESSAGEADD` with a valid application token arrives for a `DIALOG_ID` not seen before on this portal
- **THEN** the system creates an `open` conversation, persists the message with role `user`, links that dialog id to the conversation, and returns that conversation id with status `processed`

#### Scenario: Неверный токен приложения отклоняется

- **WHEN** a bot event arrives with a missing or invalid application token
- **THEN** the system responds with HTTP 403 and persists nothing

#### Scenario: Приветствие без вопроса не гоняет граф

- **WHEN** Bitrix sends a bot join or welcome event without a guest question text
- **THEN** the system does not create a guest turn, does not call `run_chat_turn`, and does not send a knowledge-base answer

### Requirement: Маппинг DIALOG_ID бота не пересекается с коннектором

The system SHALL map `(channel="bitrix_ol_bot", thread_id=DIALOG_ID, installation_id)` to `conversation_id` through the existing `ChannelThread` unique key. This mapping SHALL be distinct from `channel="bitrix_openlines"`: the same numeric/chat id on the connector path SHALL NOT reuse a bot conversation, and the reverse SHALL also hold. The first guest message of a bot dialog SHALL create the mapping; later messages of that dialog SHALL continue it.

#### Scenario: Следующие сообщения того же окна продолжают диалог

- **WHEN** a new guest message arrives for a `DIALOG_ID` whose first message created a conversation
- **THEN** the message is persisted in that same conversation and no new mapping or conversation is created

#### Scenario: Тот же id в коннекторе — другой диалог

- **WHEN** a connector session and a bot dialog share the same string id on the same portal
- **THEN** they resolve to two different conversations because the channel values differ

### Requirement: Повтор события бота не дублируется

The system SHALL treat a repeated delivery of the same bot channel message id as a duplicate: it SHALL NOT persist another message, SHALL NOT run the agent graph, SHALL NOT send `imbot.message.add` again, and SHALL respond with status `duplicate`.

#### Scenario: Повторная доставка ONIMBOTMESSAGEADD идемпотентна

- **WHEN** the same guest message id is delivered to `/webhook/bitrix/bot` a second time after a successful first processing
- **THEN** the conversation, messages and escalations are unchanged and the response has status `duplicate`

### Requirement: Ответ агента уходит в то же окно через imbot

When processing a guest bot-dialog message produces a reply for the guest, the system SHALL deliver that reply with `imbot.message.add` into the same `DIALOG_ID` after the conversation state is committed. Delivery SHALL use the stored OAuth access token, not `BITRIX_APP_TOKEN`. When processing produces no reply — an operator message or an escalation — the system SHALL NOT call `imbot.message.add`. Outbound delivery SHALL NOT use `imconnector.send.messages` on this path.

#### Scenario: Автоответ виден клиенту в том же чате Bitrix

- **WHEN** a guest message in the Open Lines bot dialog is processed with confidence at or above the threshold
- **THEN** the generated answer is persisted as an assistant message and, after commit, sent with `imbot.message.add` to that same `DIALOG_ID`

#### Scenario: Эскалация ничего не отправляет клиенту

- **WHEN** a guest bot-dialog message is processed with confidence below the threshold
- **THEN** the conversation becomes `escalated` and `imbot.message.add` is not called

#### Scenario: Сообщение оператора не активирует автоответ

- **WHEN** an Open Lines operator writes in a linked bot dialog
- **THEN** the transcript gains a single `operator` message, the graph does not run, and no bot reply is sent

#### Scenario: Эхо самого бота игнорируется

- **WHEN** `ONIMBOTMESSAGEADD` is authored by the registered Open Lines bot
- **THEN** the system persists nothing, does not run the graph, and does not send another message

### Requirement: Бот регистрируется при установке приложения

The system SHALL register an Open Lines bot (`imbot.register`, type open line) after a successful OAuth installation, using `EVENT_MESSAGE_ADD` = `POST /webhook/bitrix/bot` on the public handler base URL. The bot code SHALL come from env (`BITRIX_BOT_CODE`). The resulting bot id SHALL be persisted next to the portal's OAuth record. If a bot with that code already exists on the portal, the system SHALL reuse it instead of creating a duplicate. Re-installation SHALL update the stored bot id without breaking existing `ChannelThread` mappings.

#### Scenario: Первая установка создаёт бота открытой линии

- **WHEN** Bitrix completes `POST /webhook/bitrix/install` and no bot with `BITRIX_BOT_CODE` is stored for that `member_id`
- **THEN** the system registers the bot with the bot webhook URL, persists the bot id, and authenticates the call with the just-stored OAuth access token

#### Scenario: Повторная установка не плодит второго бота

- **WHEN** installation runs again for a portal that already has a bot with the same code
- **THEN** the system keeps a single bot and updates the stored bot id to that existing bot
