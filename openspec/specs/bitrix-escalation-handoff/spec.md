## Purpose

Сценарий 1 ТЗ ниже порога: клиенту в Bitrix ничего не уходит, оператор
получает черновик в консоли и (best-effort) заметку в том же диалоге.

## Requirements

### Requirement: Ниже порога гостю в Bitrix тишина

When a guest Bitrix bot or connector turn is processed with confidence
below the effective threshold, the system SHALL mark the conversation
`escalated`, persist one `Escalation` row, and SHALL NOT call
`imbot.message.add` or `imconnector.send.messages` with the draft or any
guest-facing answer.

#### Scenario: Эскалация не пишет клиенту

- **WHEN** a guest message on an `open` Bitrix bot dialog scores below the threshold
- **THEN** status is `escalated`, one Escalation row exists, and no guest-facing Bitrix REST send is made

### Requirement: Канальная эскалация заполняет черновик оператора

After the escalation state is committed on a Bitrix (or Redmine) guest
turn, the system SHALL call `generate_draft` and store the result in
`Conversation.suggested_response`. That text SHALL NOT be sent to the
guest. Failure to generate SHALL leave `suggested_response` empty and
SHALL NOT roll back the escalation.

#### Scenario: Оператор видит черновик в консоли

- **WHEN** a Bitrix guest turn first escalates and generate_draft returns text
- **THEN** `suggested_response` equals that text, the guest transcript has no assistant answer, and the conversation stays `escalated`

#### Scenario: Ошибка generate не откатывает эскалацию

- **WHEN** generate_draft fails after the escalation commit
- **THEN** status remains `escalated`, `suggested_response` is empty, and the operator can still use on-demand suggest

### Requirement: Операторская заметка в диалоге Bitrix не видна гостю

When `suggested_response` is stored after a Bitrix escalation, the system
SHALL attempt to deliver that text as an operator-only note in the same
dialog after commit. Delivery SHALL NOT use the guest reply methods
`imbot.message.add` (guest) or `imconnector.send.messages`. REST failure
SHALL be logged without secrets and SHALL NOT change conversation status.

#### Scenario: Заметка не уходит как ответ бота клиенту

- **WHEN** a Bitrix escalation stores a draft and operator-note REST is configured
- **THEN** the guest reply send is not called and the note attempt happens after commit

#### Scenario: Сбой заметки не снимает эскалацию

- **WHEN** the operator-note REST call fails
- **THEN** the conversation stays `escalated` and `suggested_response` is unchanged

### Requirement: Assist mode `agent` keeps Bitrix guest silent even above threshold

When effective assist mode is `agent` and a Bitrix bot or connector
guest turn produces a generated answer at or above the confidence threshold,
the system SHALL follow the same guest-silence path as a below-threshold
escalation: no `imbot.message.add` or `imconnector.send.messages` with that
answer, conversation `escalated`, and `suggested_response` filled by the
shared delivery gate (or `fill_escalation_draft` if the graph did not
generate). Channel adapters SHALL NOT implement a second assist-mode `agent`
branch; they SHALL keep using `ChatResponse.escalated` after `run_chat_turn`.

#### Scenario: High-confidence Bitrix reply is held

- **WHEN** assist mode is `agent` and a guest Bitrix bot question scores
  at or above the threshold
- **THEN** status is `escalated`, `suggested_response` holds the generated
  text, and no guest-facing Bitrix REST send is made
