## Purpose

Сценарий 2 ТЗ на живом портале: агент слушает уже идущий чат пользователь ↔
оператор в той же линии/онлайн-чате (события бота и коннектора), без нового
публичного URL. Импровизированный `POST /webhook/bitrix` остаётся.

## ADDED Requirements

### Requirement: После оператора гость в draft получает черновик, не автоответ

When a Bitrix bot or connector guest message arrives for a conversation
that is `escalated` or already has an operator message, and effective
assist mode is `draft`, the system SHALL persist the user message, run
`generate_draft`, store `suggested_response`, SHALL NOT run the full
guest-facing auto-reply send, and SHALL NOT change status away from
`escalated` (or SHALL leave `open` unchanged if only an operator message
exists and status is still `open`).

#### Scenario: Реплика гостя после эскалации в draft

- **WHEN** an already `escalated` Bitrix bot dialog receives a new guest message in `draft` mode
- **THEN** a user message is stored, `suggested_response` is updated from generate_draft, and `imbot.message.add` is not called for a guest answer

#### Scenario: Реплика гостя после сообщения оператора в draft

- **WHEN** a Bitrix dialog that already has a `role=operator` message receives a guest message in `draft` mode
- **THEN** a draft is stored for the operator and no guest-facing Bitrix reply is sent

### Requirement: Auto после оператора отвечает гостю тем же ядром

When the same post-operator (or already `escalated`) Bitrix guest message
arrives and effective assist mode is `auto`, the system SHALL process it
through `run_chat_turn`. A high-confidence answer SHALL be delivered to
the guest with the same outbound method as scenario 1 for that path
(`imbot.message.add` or `imconnector.send.messages`) after commit. A
below-threshold result SHALL follow `bitrix-escalation-handoff`.

#### Scenario: Auto отвечает гостю в том же окне

- **WHEN** assist mode is `auto` and a guest follow-up on an escalated Bitrix bot dialog scores at or above the threshold
- **THEN** the generated answer is sent to that same `DIALOG_ID` with `imbot.message.add` after commit

### Requirement: Импровизированный live-вебхук не удаляется

The system SHALL keep `POST /webhook/bitrix` (internal token,
`channel="bitrix"`, `live_thread`) available. Adding portal scenario 2
SHALL NOT remove, rename, or reuse that path.

#### Scenario: Внутренний вебхук жив

- **WHEN** portal bot and connector scenario-2 handling is present
- **THEN** `POST /webhook/bitrix` still accepts a live-thread event with the internal token

### Requirement: Сообщение оператора по-прежнему не гоняет граф

An operator message on the Bitrix bot or connector path SHALL persist as
`role=operator` and SHALL NOT run `run_chat_turn` or `generate_draft`.

#### Scenario: Оператор пишет в линии

- **WHEN** an Open Lines operator writes in a linked bot dialog
- **THEN** the transcript gains a single operator message and no draft or guest reply is sent
