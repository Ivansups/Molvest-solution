## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Handoff detection runs a lightweight LLM

After `classify` sets intent `support`, before any cache lookup or retrieve, the system SHALL run a `handoff_detect` node that asks a lightweight LLM classifier via OpenRouter whether the user asks to hand the dialog to a human. The classifier SHALL return a strict YES/NO. A `YES` SHALL set intent `handoff`, `escalated=true` and `escalation_reason` to the handoff reason, and the graph SHALL end without a cache lookup, retrieve, or generate. A `NO` SHALL keep intent `support` and continue to the answer cache lookup. A classifier failure (network, HTTP, or unparseable reply) SHALL fall back to `support` and continue the normal path. When the OpenRouter API key is empty, detection SHALL be skipped and the graph SHALL continue as if `NO`.

#### Scenario: Imperative handoff escalates before RAG

- **WHEN** the user sends «позовите оператора» and the classifier returns `YES`
- **THEN** intent is `handoff`, `escalated=true`, `escalation_reason` is the handoff reason, and the graph ends without cache lookup, retrieve, or generate

#### Scenario: Desire for a human escalates before RAG

- **WHEN** the user sends «нужен человек» or «хочу поговорить с человеком» and the classifier returns `YES`
- **THEN** intent is `handoff`, `escalated=true`, and the graph ends without retrieve or generate

#### Scenario: How-to question about an operator stays support

- **WHEN** the user sends «как позвать оператора в 1С» or «как связаться с оператором» and the classifier returns `NO`
- **THEN** intent is `support` and the graph continues to retrieve / generate

#### Scenario: Classifier failure falls back to support

- **WHEN** the classifier raises or returns an unparseable answer
- **THEN** intent stays `support` and the graph continues to retrieve / generate without failing the turn

#### Scenario: Empty API key disables detection

- **WHEN** the OpenRouter API key is empty and the user sends «позовите оператора»
- **THEN** the detector is not invoked and the graph continues the normal support path