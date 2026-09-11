## Purpose

Orchestrate guest support turns: classify only empty vs. non-empty without GigaChat, detect an explicit handoff to a human, then cache or retrieve and generate for every real question — no canned template ever substitutes for a model call.

## Requirements

### Requirement: Classify only filters empty input

The classify node SHALL run without calling GigaChat and SHALL distinguish only `empty` from `support`. An empty (or whitespace-only) query SHALL be `empty`. Every non-empty query — including greetings, thanks, and off-topic phrasing — SHALL be `support` and continue to the `handoff_detect` node. The system SHALL NOT special-case greeting or off-topic text with a canned reply that skips GigaChat.

#### Scenario: Greeting plus a 1C question is support

- **WHEN** the user sends «привет, как провести документ в 1С»
- **THEN** intent is `support` and the graph continues to `handoff_detect`

#### Scenario: Thanks still reaches the model

- **WHEN** the user sends «спасибо»
- **THEN** intent is `support` and the graph continues to `handoff_detect` / retrieve / generate, not a canned greeting reply

#### Scenario: Ambiguous IT question is support

- **WHEN** the user sends «не понимаю как поднять сервер»
- **THEN** intent is `support` and the graph continues to `handoff_detect`

#### Scenario: Off-topic phrasing still reaches the model

- **WHEN** the user sends «какая у вас погода»
- **THEN** intent is `support` and the graph continues to `handoff_detect` / retrieve / generate, not a canned off-topic reply

### Requirement: Only empty input uses a template

For intent `empty` the system SHALL return a fixed template and SHALL NOT call GigaChat `generate`. Intent `handoff` SHALL also skip the model, but SHALL return the guest escalation phrase (see conversation-records) rather than the empty template. Greeting and off-topic text no longer exist as separate intents.

#### Scenario: Empty skips the model

- **WHEN** the user sends no text and no image
- **THEN** the response text is the empty-input template and GigaChat is not called

#### Scenario: Handoff returns the escalation phrase

- **WHEN** the user sends a handoff request
- **THEN** GigaChat is not called and the response text is the guest escalation phrase, not the empty template

### Requirement: Handoff detection runs a lightweight LLM

After `classify` sets intent `support`, before any cache lookup or retrieve, the system SHALL run a `handoff_detect` node that asks a lightweight LLM classifier whether the user asks to hand the dialog to a human. The primary classifier is OpenRouter. When the OpenRouter API key is empty or OpenRouter fails (network, HTTP, or unparseable reply), the same YES/NO prompt SHALL be sent to GigaChat-2 (Lite). The classifier SHALL return a strict YES/NO. A `YES` SHALL set intent `handoff`, `escalated=true` and `escalation_reason` to the handoff reason, and the graph SHALL end without a cache lookup, retrieve, or generate. A `NO` SHALL keep intent `support` and continue to the answer cache lookup. If both classifiers fail, the system SHALL escalate with the detector-failure reason and SHALL NOT continue to retrieve or generate.

#### Scenario: Imperative handoff escalates before RAG

- **WHEN** the user sends «позовите оператора» and the classifier returns `YES`
- **THEN** intent is `handoff`, `escalated=true`, `escalation_reason` is the handoff reason, and the graph ends without cache lookup, retrieve, or generate

#### Scenario: Desire for a human escalates before RAG

- **WHEN** the user sends «нужен человек» or «хочу поговорить с человеком» and the classifier returns `YES`
- **THEN** intent is `handoff`, `escalated=true`, and the graph ends without retrieve or generate

#### Scenario: How-to question about an operator stays support

- **WHEN** the user sends «как позвать оператора в 1С» or «как связаться с оператором» and the classifier returns `NO`
- **THEN** intent is `support` and the graph continues to retrieve / generate

#### Scenario: OpenRouter failure falls back to GigaChat

- **WHEN** OpenRouter raises or returns an unparseable answer and GigaChat-2 returns `YES`
- **THEN** intent is `handoff`, `escalated=true`, and the graph ends without retrieve or generate

#### Scenario: Both classifiers fail escalates

- **WHEN** OpenRouter fails and GigaChat-2 also raises or returns an unparseable answer
- **THEN** intent is `handoff`, `escalated=true`, the reason is the detector-failure reason, and the graph does not retrieve or generate

#### Scenario: Empty OpenRouter key uses GigaChat

- **WHEN** the OpenRouter API key is empty and the user sends «позовите оператора» and GigaChat-2 returns `YES`
- **THEN** OpenRouter is not invoked, intent is `handoff`, and the graph ends without retrieve or generate

### Requirement: Forced handoff skips the classifier

When the incoming chat request has `force_handoff=true`, the `handoff_detect`
node SHALL set intent `handoff`, `escalated=true`, and the explicit handoff
reason without calling OpenRouter or GigaChat. The graph SHALL then end
without cache lookup, retrieve, or generate. This path SHALL work even if
the query is a short canned phrase. The graph SHALL NOT inspect which
channel produced the request.

#### Scenario: Flag escalates without NLP

- **WHEN** `force_handoff` is true and the text is the widget canned handoff
  phrase
- **THEN** intent is `handoff`, OpenRouter and GigaChat classify are not
  called, and retrieve/generate do not run

#### Scenario: Ordinary message still uses the classifier

- **WHEN** `force_handoff` is false or omitted and the user sends a support
  question
- **THEN** `handoff_detect` still runs the lightweight YES/NO classifier

### Requirement: Answer cache is checked before retrieve

After `handoff_detect` keeps intent `support`, the system SHALL look up the Redis answer cache keyed by `kb_version` and the normalized question. A hit SHALL return that text and SHALL NOT call retrieve or generate. A miss SHALL continue to retrieve. The system SHALL write the cache only after a successful generate that is not an escalation. Greeting and escalated answers SHALL NOT be written.

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
