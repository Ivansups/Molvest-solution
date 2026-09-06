## Purpose

Orchestrate guest support turns: classify only empty vs. non-empty without GigaChat, cache or retrieve, then generate for every real question — no canned template ever substitutes for a model call.

## Requirements

### Requirement: Classify only filters empty input

The classify node SHALL run without calling GigaChat and SHALL only distinguish `empty` from `support`. An empty (or whitespace-only) query SHALL be `empty`. Every non-empty query — including greetings, thanks, and off-topic phrasing — SHALL be `support` and continue to retrieve / generate. The system SHALL NOT special-case greeting or off-topic text with a canned reply that skips GigaChat, since doing so would answer without ever consulting the model.

#### Scenario: Greeting plus a 1C question is support

- **WHEN** the user sends «привет, как провести документ в 1С»
- **THEN** intent is `support` and the graph continues to retrieve

#### Scenario: Thanks still reaches the model

- **WHEN** the user sends «спасибо»
- **THEN** intent is `support` and the graph continues to retrieve / generate, not a canned greeting reply

#### Scenario: Ambiguous IT question is support

- **WHEN** the user sends «не понимаю как поднять сервер»
- **THEN** intent is `support` and the graph continues to retrieve

#### Scenario: Off-topic phrasing still reaches the model

- **WHEN** the user sends «какая у вас погода»
- **THEN** intent is `support` and the graph continues to retrieve / generate, not a canned off-topic reply

### Requirement: Only empty input uses a template

For intent `empty` the system SHALL return a fixed template and SHALL NOT call GigaChat `generate`. This is the only intent allowed to skip the model — greeting and off-topic text no longer exist as separate intents.

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
