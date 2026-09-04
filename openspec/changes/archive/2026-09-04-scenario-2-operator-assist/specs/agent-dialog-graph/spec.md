## ADDED Requirements

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
