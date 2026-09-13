## Purpose

Orchestrate guest support turns: classify only empty vs. non-empty without GigaChat, route each turn with a lightweight LLM (intake router), then cache or retrieve and generate on GigaChat for every real support question — greetings, away checks, off-topic, and explicit handoffs are answered or escalated by the router before RAG.

## Requirements

### Requirement: Classify only filters empty input

The classify node SHALL run without calling GigaChat and SHALL distinguish
only `empty` from `support`. An empty (or whitespace-only) query SHALL be
`empty`. Every non-empty query SHALL be `support` and continue to the
`router` node. Classify SHALL NOT itself special-case greetings, thanks, or
off-topic text — that is the router's job.

#### Scenario: Greeting plus a 1C question is support

- **WHEN** the user sends «привет, как провести документ в 1С»
- **THEN** intent is `support` and the graph continues to the `router` node

#### Scenario: Thanks still reaches the model

- **WHEN** the user sends «спасибо»
- **THEN** the router invokes the lightweight model and answers with the short
  greeting reply; GigaChat `generate` is not called

#### Scenario: Ambiguous IT question is support

- **WHEN** the user sends «не понимаю как поднять сервер»
- **THEN** intent is `support` and the graph continues to the `router` node

#### Scenario: Off-topic phrasing still reaches the model

- **WHEN** the user sends «какая у вас погода»
- **THEN** the router invokes the lightweight model and answers with the short
  off-topic reply; GigaChat `generate` is not called

### Requirement: Only empty input uses a template

For intent `empty` the system SHALL return a fixed template and SHALL NOT
call GigaChat `generate`. Intent `handoff` SHALL also skip the model, but
SHALL return the guest escalation phrase (see conversation-records) rather
than the empty template. Intents `greeting`, `away`, and `offtopic` SHALL
return a short reply — the small model's reply or a fixed default template —
with `confidence=1.0` and `escalated=false`, SHALL NOT call GigaChat, and
SHALL NOT be written to the answer cache.

#### Scenario: Empty skips the model

- **WHEN** the user sends no text and no image
- **THEN** the response text is the empty-input template and GigaChat is not
  called

#### Scenario: Handoff returns the escalation phrase

- **WHEN** the user sends a handoff request
- **THEN** GigaChat is not called and the response text is the guest
  escalation phrase, not the empty template

#### Scenario: Greeting returns a short reply without the model

- **WHEN** the user sends a bare greeting
- **THEN** the response is the short greeting reply, `confidence` is 1.0,
  and GigaChat is not called

#### Scenario: Away check returns a short reply without the model

- **WHEN** the user sends a bare away check such as «ты тут?»
- **THEN** the response is the short away reply and GigaChat is not called

#### Scenario: Off-topic returns a short reply without the model

- **WHEN** the user sends bare off-topic text
- **THEN** the response is the short off-topic reply and GigaChat is not
  called

### Requirement: Handoff detection runs a lightweight LLM

After `classify` sets intent `support`, before any cache lookup or retrieve,
the system SHALL run a `router` node that asks a lightweight LLM classifier
which route the turn takes. The primary classifier is OpenRouter. The
classifier SHALL return a strict reply: a code word on the first line
(`SUPPORT`, `HANDOFF`, `GREETING`, `AWAY_CHECK`, or `OFFTOPIC`) and an
optional short reply on the following lines. An unparseable or empty reply
SHALL be treated as a classifier failure, never as `support`. The node SHALL
route the guest text, not the Vision dump.
A `HANDOFF` SHALL set intent `handoff`, `escalated=true` and
`escalation_reason` to the handoff reason, and the graph SHALL end without a
cache lookup, retrieve, or generate. A `SUPPORT` SHALL set intent `support`
and continue to the answer cache lookup. A `GREETING`, `AWAY_CHECK`, or
`OFFTOPIC` SHALL answer with the short reply (or its default template) and
end the graph without retrieve or generate.
When the OpenRouter API key is empty or OpenRouter fails (network, HTTP, or
unparseable reply), the system SHALL first apply regex rules for short,
unambiguous greetings, away checks, and handoff requests, tolerant of
trailing punctuation `.`, `!`, `,`, and `?`. If the rules do not decide, the
system SHALL send the YES/NO handoff prompt to GigaChat-2 (Lite). If both
classifiers and the rules fail to decide, the system SHALL escalate with the
detector-failure reason and SHALL NOT continue to retrieve or generate.

#### Scenario: Imperative handoff escalates before RAG

- **WHEN** the user sends «позовите оператора» and the classifier returns
  `HANDOFF`
- **THEN** intent is `handoff`, `escalated=true`, `escalation_reason` is the
  handoff reason, and the graph ends without cache lookup, retrieve, or
  generate

#### Scenario: Desire for a human escalates before RAG

- **WHEN** the user sends «нужен человек» or «хочу поговорить с человеком»
  and the classifier returns `HANDOFF`
- **THEN** intent is `handoff`, `escalated=true`, and the graph ends without
  retrieve or generate

#### Scenario: How-to question about an operator stays support

- **WHEN** the user sends «как позвать оператора в 1С» or
  «как связаться с оператором» and the classifier returns `SUPPORT`
- **THEN** intent is `support` and the graph continues to retrieve / generate

#### Scenario: Bare greeting answers without the heavy model

- **WHEN** the user sends «привет» and the classifier returns `GREETING`
- **THEN** intent is `greeting`, the response is the short greeting reply,
  and the graph ends without cache lookup, retrieve, or generate

#### Scenario: Away check answers without the heavy model

- **WHEN** the user sends «ты тут?» and the classifier returns `AWAY_CHECK`
- **THEN** intent is `away`, the response is the short away reply, and the
  graph ends without retrieve or generate

#### Scenario: Router ignores the Vision dump

- **WHEN** the turn includes an image whose Vision dump differs from the
  guest text
- **THEN** the router classifies the guest text, not the dump

#### Scenario: Unparseable small-model reply fails closed

- **WHEN** OpenRouter returns a reply without a recognized code word
- **THEN** the reply is treated as a classifier failure and the system never
  treats it as `support`; the fallback chain decides the route

#### Scenario: OpenRouter failure falls back to GigaChat

- **WHEN** OpenRouter raises or returns an unparseable answer, the regex
  rules do not decide, and GigaChat-2 returns `YES`
- **THEN** intent is `handoff`, `escalated=true`, and the graph ends without
  retrieve or generate

#### Scenario: Both classifiers fail escalates

- **WHEN** OpenRouter fails, the regex rules do not decide, and GigaChat-2
  also raises or returns an unparseable answer
- **THEN** intent is `handoff`, `escalated=true`, the reason is the
  detector-failure reason, and the graph does not retrieve or generate

#### Scenario: Empty OpenRouter key uses GigaChat

- **WHEN** the OpenRouter API key is empty, the regex rules do not decide,
  and the user sends a handoff request and GigaChat-2 returns `YES`
- **THEN** OpenRouter is not invoked, intent is `handoff`, and the graph ends
  without retrieve or generate

### Requirement: Forced handoff skips the classifier

When the incoming chat request has `force_handoff=true`, the `router` node
SHALL set intent `handoff`, `escalated=true`, and the explicit handoff reason
without calling OpenRouter or GigaChat. The graph SHALL then end without
cache lookup, retrieve, or generate. This path SHALL work even if the query
is a short canned phrase. The graph SHALL NOT inspect which channel produced
the request.

#### Scenario: Flag escalates without NLP

- **WHEN** `force_handoff` is true and the text is the widget canned handoff
  phrase
- **THEN** intent is `handoff`, OpenRouter and GigaChat classify are not
  called, and retrieve/generate do not run

#### Scenario: Ordinary message still uses the classifier

- **WHEN** `force_handoff` is false or omitted and the user sends a support
  question
- **THEN** the `router` node still runs the lightweight classifier

### Requirement: Answer cache is checked before retrieve

After the `router` node keeps intent `support`, the system SHALL look up the
Redis answer cache keyed by `kb_version` and the normalized question. A hit
SHALL return that text and SHALL NOT call retrieve or generate. A miss SHALL
continue to retrieve. The system SHALL write the cache only after a
successful generate that is not an escalation. Greeting and escalated answers
SHALL NOT be written.

#### Scenario: Repeat question hits cache

- **WHEN** the same support question is asked again while `kb_version` is
  unchanged
- **THEN** the second response comes from cache and generate is not called

#### Scenario: Escalation is not cached

- **WHEN** retrieve scores below the confidence threshold
- **THEN** the graph does not call generate and does not write an answer
  cache entry

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
</content>
