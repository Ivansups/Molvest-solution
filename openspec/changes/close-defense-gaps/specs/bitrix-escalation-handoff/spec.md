## ADDED Requirements

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
