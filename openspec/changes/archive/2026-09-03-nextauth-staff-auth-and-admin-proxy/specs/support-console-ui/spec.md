## MODIFIED Requirements

### Requirement: Protected support routes require a support session

The system SHALL treat `/`, `/chat/support`, `/chat/support/:ticketId`,
`/knowledge-base`, `/settings`, `/analytics`, and `/operator` as support
console routes. A user without a support session SHALL be redirected to
`/login`. The support login form at `/login` SHALL use empty inputs with
placeholders instead of prefilled credentials.

#### Scenario: Guest opens a protected route

- **WHEN** a user without a support session opens `/knowledge-base`
- **THEN** the system redirects the user to `/login`
