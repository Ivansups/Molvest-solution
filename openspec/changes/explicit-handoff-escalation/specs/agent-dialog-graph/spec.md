## MODIFIED Requirements

### Requirement: Classify only filters empty input

The classify node SHALL run without calling GigaChat and SHALL distinguish `empty`, `handoff`, and `support`. An empty (or whitespace-only) query SHALL be `empty`. A query that explicitly asks to hand the dialog to a human — imperative «позовите/вызовите/передайте/соедините/переключите/пригласите/свяжите/переведите … оператора/специалиста/человека», desire «нужен человек», «хочу поговорить с человеком» — SHALL be `handoff` and SHALL escalate without a cache lookup, retrieve, or generate. A query that only asks about an operator as a subject («как позвать оператора в 1С», «как связаться с оператором», «можно ли позвать оператора») SHALL be `support`. Every other non-empty query — including greetings, thanks, and off-topic phrasing — SHALL be `support` and continue to retrieve / generate. The system SHALL NOT special-case greeting or off-topic text with a canned reply that skips GigaChat.

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

#### Scenario: Imperative handoff escalates before RAG

- **WHEN** the user sends «позовите оператора»
- **THEN** intent is `handoff`, `escalated=true`, and the graph ends without cache lookup, retrieve, or generate

#### Scenario: Desire for a human escalates before RAG

- **WHEN** the user sends «нужен человек» or «хочу поговорить с человеком»
- **THEN** intent is `handoff`, `escalated=true`, and the graph ends without retrieve or generate

#### Scenario: How-to question about an operator stays support

- **WHEN** the user sends «как позвать оператора в 1С» or «как связаться с оператором»
- **THEN** intent is `support` and the graph continues to retrieve / generate

### Requirement: Only empty input uses a template

For intent `empty` the system SHALL return a fixed template and SHALL NOT call GigaChat `generate`. Intent `handoff` SHALL also skip the model, but SHALL return the guest escalation phrase (see conversation-records) rather than the empty template. Greeting and off-topic text no longer exist as separate intents.

#### Scenario: Empty skips the model

- **WHEN** the user sends no text and no image
- **THEN** the response text is the empty-input template and GigaChat is not called

#### Scenario: Handoff returns the escalation phrase

- **WHEN** the user sends a handoff request
- **THEN** GigaChat is not called and the response text is the guest escalation phrase, not the empty template