## Purpose

Orchestrate guest support turns: classify without GigaChat, cache or retrieve, then generate only when needed.

## Requirements

### Requirement: Classify prefers support over greeting

The classify node SHALL run without calling GigaChat. An empty query SHALL be `empty`. If the text matches support keywords it SHALL be `support`, even when a greeting word is also present. Otherwise a greeting or thanks match SHALL be `greeting`. Queries that match explicit off-topic phrases SHALL be `off_topic`. Everything else SHALL be `support` (retrieve / escalate), not a canned off-topic template.

#### Scenario: Greeting plus a 1C question is support

- **WHEN** the user sends «привет, как провести документ в 1С»
- **THEN** intent is `support` and the graph continues to retrieve

#### Scenario: Thanks is greeting

- **WHEN** the user sends «спасибо»
- **THEN** intent is `greeting` and retrieve is not called

#### Scenario: Ambiguous IT question is support

- **WHEN** the user sends «не понимаю как поднять сервер»
- **THEN** intent is `support` and the graph continues to retrieve

#### Scenario: Explicit off-topic stays canned

- **WHEN** the user sends «какая у вас погода»
- **THEN** intent is `off_topic` and retrieve is not called

### Requirement: Greeting, thanks, empty, and off-topic use templates

For intents `empty`, `greeting`, and `off_topic` the system SHALL return a fixed template and SHALL NOT call GigaChat `generate`.

#### Scenario: Greeting skips the model

- **WHEN** the user sends «привет»
- **THEN** the response text is the greeting template and `generate` is not called

#### Scenario: Empty skips the model

- **WHEN** the user sends no text and no image
- **THEN** the response text is the empty-input template and GigaChat is not called

### Requirement: Answer cache is checked before retrieve

After classify, when intent is `support`, the system SHALL look up the Redis answer cache keyed by `kb_version` and the normalized question. A hit SHALL return that text and SHALL NOT call retrieve or generate. A miss SHALL continue to retrieve. The system SHALL write the cache only after a successful generate that is not an escalation. Greeting and escalated answers SHALL NOT be written.

#### Scenario: Repeat question hits cache

- **WHEN** the same support question is asked again while `kb_version` is unchanged
- **THEN** the second response comes from cache and generate is not called

#### Scenario: Escalation is not cached

- **WHEN** retrieve scores below the confidence threshold
- **THEN** the graph does not call generate and does not write an answer cache entry

### Requirement: Generate uses the last messages of the conversation

When `conversation_id` points to an existing conversation, `generate` SHALL include the last 3 or 4 persisted messages as context. The graph SHALL NOT open its own database session to load them.

#### Scenario: Follow-up uses prior turns

- **WHEN** a user asks a short follow-up in an existing conversation that already has messages
- **THEN** those recent messages are present in the generate prompt

### Requirement: Escalated draft guest turns skip GigaChat

When assist mode is `draft` and conversation status is already `escalated`, a guest support turn SHALL NOT look up the answer cache, SHALL NOT retrieve, and SHALL NOT call generate. The graph SHALL accept `conversation_status` in state and SHALL NOT open a database session. Weak-score turns on an `open` conversation SHALL still retrieve to decide escalation and SHALL still skip generate.

#### Scenario: Follow-up in draft skips the model

- **WHEN** assist mode is `draft` and an already `escalated` conversation receives a support question
- **THEN** generate is not called and retrieve is not called

#### Scenario: Open conversation still caches repeats

- **WHEN** the same support question is asked again on an `open` conversation while `kb_version` is unchanged
- **THEN** the second response comes from cache and generate is not called

#### Scenario: Weak score on open still skips generate

- **WHEN** retrieve scores below the confidence threshold on an `open` conversation
- **THEN** the graph does not call generate and does not write an answer cache entry
