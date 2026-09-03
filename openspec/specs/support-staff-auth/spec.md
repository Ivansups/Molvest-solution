## Purpose

Support staff authentication for the internal console, including persistent
`NextAuth` sessions, Prisma-managed auth tables, and seeded demo users.

## Requirements

### Requirement: Staff login uses NextAuth with Prisma-backed users and sessions

The system SHALL authenticate support staff in `frontend/` via `NextAuth`
Credentials and persist users and sessions in Prisma-managed Postgres auth
tables that do not overlap with domain tables managed by Alembic.

#### Scenario: Staff user signs in

- **WHEN** a support employee submits a valid email and password on `/login`
- **THEN** the system creates or reuses a `NextAuth` session stored in the auth
  tables and grants access to the support console

### Requirement: Demo support users are seeded explicitly

The system SHALL seed at least two demo staff users:
`admin@molvest.ru` and `operator@molvest.ru`. The system SHALL NOT accept an
arbitrary password for arbitrary email in the target scenario.

#### Scenario: Demo users exist for local verification

- **WHEN** the auth seed is applied
- **THEN** the database contains the admin and operator demo accounts with
  stored password hashes

### Requirement: Legacy HMAC support auth is not part of the target flow

The system SHALL use a single staff auth flow and SHALL NOT keep the old
HMAC/mock support cookie as a parallel login mechanism for the support console.

#### Scenario: Support console reads the NextAuth session

- **WHEN** a staff user opens a protected console route
- **THEN** authorization is determined from the `NextAuth` session rather than
  a legacy local mock cookie
