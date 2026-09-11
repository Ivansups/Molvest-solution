## MODIFIED Requirements

### Requirement: Read effective agent settings

The system SHALL provide `GET /api/settings` (protected by the same internal
service token as other admin APIs) returning the effective
`confidence_threshold` (float) and `operator_assist_mode` (`draft`, `auto`,
or `agent`). Settings value `agent` means every AI reply is a draft until
the operator clicks Send; it is not the LangGraph agent. When no runtime
override exists, values SHALL match the process environment / application
config defaults.

#### Scenario: Defaults from environment

- **WHEN** a client calls `GET /api/settings` after a fresh API start with
  `CONFIDENCE_THRESHOLD=0.8` and `OPERATOR_ASSIST_MODE=draft`
- **THEN** the response body contains `confidence_threshold` 0.8 and
  `operator_assist_mode` `"draft"`

#### Scenario: Settings value agent is readable

- **WHEN** the effective assist mode is `agent`
- **THEN** `GET /api/settings` returns `operator_assist_mode` `"agent"`

### Requirement: Update effective agent settings

The system SHALL provide `PUT /api/settings` accepting `confidence_threshold`
in range 0.5–0.99 inclusive and `operator_assist_mode` of `draft`, `auto`, or
`agent`. After a successful update, subsequent guest turns SHALL use
the new threshold for escalation decisions and the new assist mode for
delivery policy, without requiring an API process restart. Invalid bodies
SHALL return 422. Values `draft` and `auto` SHALL keep their previous
semantics.

#### Scenario: Threshold change affects escalation

- **WHEN** an admin sets `confidence_threshold` to 0.95 via `PUT /api/settings`
  and a guest support question then retrieves a best chunk score of 0.9
- **THEN** the turn escalates without calling generate

#### Scenario: Invalid threshold rejected

- **WHEN** a client sends `PUT /api/settings` with `confidence_threshold`
  below 0.5 or above 0.99
- **THEN** the API returns 422 and effective settings are unchanged

#### Scenario: Assist mode change is visible on readback

- **WHEN** an admin sets `operator_assist_mode` to `auto` via
  `PUT /api/settings`
- **THEN** a following `GET /api/settings` returns `operator_assist_mode`
  `"auto"`

#### Scenario: Settings value agent is accepted

- **WHEN** an admin sets `operator_assist_mode` to `agent` via
  `PUT /api/settings`
- **THEN** a following `GET /api/settings` returns `operator_assist_mode`
  `"agent"`

#### Scenario: Unknown assist mode rejected

- **WHEN** a client sends `PUT /api/settings` with `operator_assist_mode`
  `"require_operator_confirm"` or another unknown value
- **THEN** the API returns 422 and effective settings are unchanged
