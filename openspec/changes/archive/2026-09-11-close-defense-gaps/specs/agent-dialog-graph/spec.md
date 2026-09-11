## ADDED Requirements

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
