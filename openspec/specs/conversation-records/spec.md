## Purpose

Persist conversations, messages, and escalations. Status may change only through the transition service. There is no public conversation HTTP API yet.

## Requirements

### Requirement: Conversation tables exist

The system SHALL persist Conversation, Message, and Escalation rows in PostgreSQL with the fields defined in roadmap Stage 2. Conversation.status SHALL be one of `open`, `escalated`, `resolved`. Message.role SHALL be one of `user`, `assistant`, `system`. Timestamps SHALL be stored in UTC. The first Alembic revision SHALL create these tables with named indexes and foreign keys.

#### Scenario: Migration creates conversation tables

- **WHEN** an operator runs Alembic upgrade to head against an empty database
- **THEN** Conversation, Message, and Escalation tables exist with the expected columns

### Requirement: Status changes only through the transition service

The system SHALL change `Conversation.status` only through a single transition service. Allowed transitions are `open → escalated` and `escalated → resolved`. Any other assignment, including direct writes from a router or graph node, is out of contract. An illegal transition SHALL raise a domain error and SHALL NOT persist.

#### Scenario: Legal escalation

- **WHEN** the transition service is asked to move a conversation from `open` to `escalated`
- **THEN** the stored status becomes `escalated`

#### Scenario: Illegal skip

- **WHEN** the transition service is asked to move a conversation from `open` to `resolved`
- **THEN** the call fails and the stored status stays `open`

#### Scenario: Illegal backward move

- **WHEN** the transition service is asked to move a conversation from `escalated` to `open`
- **THEN** the call fails and the stored status stays `escalated`

### Requirement: No public conversation API

The system SHALL NOT expose HTTP routes for listing, creating, or updating conversations, messages, or escalations. `POST /chat` SHALL keep its current behavior and SHALL NOT be required to write these tables yet.

#### Scenario: Chat is unchanged

- **WHEN** a client calls `POST /chat`
- **THEN** the response contract is unchanged and no new conversation routes appear in OpenAPI
