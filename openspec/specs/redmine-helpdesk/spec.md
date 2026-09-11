## Purpose

Канал ТЗ «почта / Redmine HelpDesk»: вопрос в тикете доходит до того же
ядра, ответ уходит в тот же тикет, ниже порога — эскалация с черновиком
оператору, без автоответа в письмо.

## Requirements

### Requirement: Входящий вебхук Redmine принимает тикет

The system SHALL expose `POST /webhook/redmine` authenticated with the
internal service token. Each event SHALL carry `ticket_id`, `message_id`,
`sender` (`user` or `operator`), optional `text`, and optional image.
A missing or invalid token SHALL return HTTP 403 without changing state.

#### Scenario: Первое письмо тикета создаёт диалог

- **WHEN** a user event with a valid internal token arrives for a `ticket_id` not seen before
- **THEN** the system creates an `open` conversation, maps that ticket id, and returns status `processed`

#### Scenario: Неверный токен отклоняется

- **WHEN** a Redmine event arrives without a valid internal token
- **THEN** the system responds with HTTP 403 and persists nothing

### Requirement: Маппинг номера тикета не пересекается с Bitrix

The system SHALL map `(channel="redmine", thread_id=ticket_id, installation_id)`
through `ChannelThread`. The same numeric id on a Bitrix channel SHALL NOT
reuse a Redmine conversation.

#### Scenario: Повтор тикета продолжает диалог

- **WHEN** a new user message arrives for a ticket whose first message created a conversation
- **THEN** the message is persisted in that conversation and no new mapping is created

### Requirement: Повтор события тикета идемпотентен

A repeated `(channel="redmine", message_id)` SHALL NOT persist another
message, SHALL NOT run the graph, SHALL NOT send outbound mail/notes, and
SHALL respond with status `duplicate`.

#### Scenario: Дубль вебхука

- **WHEN** the same Redmine `message_id` is posted twice after a successful first processing
- **THEN** the conversation is unchanged and the response status is `duplicate`

### Requirement: Ответ агента уходит в тот же тикет

When a Redmine user turn produces a guest-facing answer, the system SHALL
deliver it to that ticket after commit (Redmine note and/or SMTP, as
configured). A guest-facing answer happens when assist mode is not
`agent` and the turn is not an escalation. When the turn is an
operator message, an escalation, or an assist-mode `agent` hold, the system
SHALL NOT send that answer to the requester.

#### Scenario: Автоответ в тикет

- **WHEN** a user ticket message scores at or above the threshold and assist
  mode is `auto` or `draft` on an `open` conversation
- **THEN** the generated answer is persisted as assistant and, after commit,
  sent to that ticket

#### Scenario: Эскалация не пишет в тикет гостю

- **WHEN** a user ticket message scores below the threshold
- **THEN** the conversation is `escalated`, `suggested_response` is filled
  per `bitrix-escalation-handoff`, and no guest-facing ticket reply is sent

### Requirement: Assist mode `agent` does not write the generated answer into the ticket

When effective assist mode is `agent`, a Redmine user turn SHALL NOT
send the generated answer to the requester even if the retrieval score is at
or above the threshold. The turn SHALL go through the same service-layer
delivery gate as the widget and Bitrix: conversation `escalated`,
`suggested_response` filled, no guest-facing ticket note/SMTP with the model
text.

#### Scenario: Высокий скор в режиме `agent` не отвечает в тикет

- **WHEN** assist mode is `agent` and a user ticket message scores at
  or above the threshold
- **THEN** the conversation is `escalated`, `suggested_response` holds the
  generated text, and no guest-facing ticket reply is sent

### Requirement: IMAP опционален и зовёт тот же сервис

When IMAP settings are present, the system SHALL poll the mailbox and
handle each new message through the same Redmine service as the webhook.
When IMAP settings are empty, the system SHALL still accept the webhook.

#### Scenario: Пустой IMAP не ломает API

- **WHEN** the API starts without `REDMINE_IMAP_*`
- **THEN** `POST /webhook/redmine` remains available and no mail poller is required
