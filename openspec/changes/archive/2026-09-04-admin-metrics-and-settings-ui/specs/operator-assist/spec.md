## MODIFIED Requirements

### Requirement: Assist mode is a single config value

The system SHALL read operator assist mode from one effective configuration value with allowed values `draft` or `auto`. The default SHALL be `draft` (from environment `OPERATOR_ASSIST_MODE` when no runtime override is set). The setting SHALL NOT be hardcoded in graph nodes or UI. Admins SHALL be able to change the effective value through `PUT /api/settings`; the guest dialog path SHALL honor the effective value on subsequent turns without an API restart.

#### Scenario: Default is draft

- **WHEN** the setting is unset and no runtime override exists
- **THEN** the system treats assist mode as `draft`

#### Scenario: Auto is honored

- **WHEN** effective assist mode is `auto` and an already escalated conversation receives a guest support question whose retrieval score is at or above the effective confidence threshold
- **THEN** the guest-facing `POST /chat` text is the generated answer, not only the escalation phrase

#### Scenario: Runtime override via settings API

- **WHEN** an admin sets `operator_assist_mode` to `auto` through `PUT /api/settings`
- **THEN** later escalated guest turns in that API process follow `auto` behavior without restarting the process
