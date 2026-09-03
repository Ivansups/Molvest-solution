## Purpose

Support staff authentication for the internal console, including `NextAuth`
JWT sessions, Prisma-managed auth tables, and seeded demo users.

## Requirements

### Requirement: Staff login uses NextAuth with Prisma-backed users

The system SHALL authenticate support staff in `frontend/` via `NextAuth`
Credentials against users stored in Prisma-managed Postgres auth tables that do
not overlap with domain tables managed by Alembic. Because the Credentials
provider never writes a session row, the session SHALL be carried in a signed
`NextAuth` JWT cookie.

#### Scenario: Staff user signs in

- **WHEN** a support employee submits a valid email and password on `/login`
- **THEN** the system issues a `NextAuth` JWT session carrying the user id, role
  and installation id, and grants access to the support console

#### Scenario: Staff user opts out of "remember me"

- **WHEN** a support employee signs in with the "запомнить меня" checkbox cleared
- **THEN** the session cookie SHALL have no expiry and end with the browser session

### Requirement: Roles are accepted only from an explicit stored value

The system SHALL derive a staff role only from an explicit known role value
(`admin` or `operator`). An absent, empty or unknown role SHALL deny the
session rather than fall back to a privileged role.

#### Scenario: Unknown role denies access

- **WHEN** a staff row carries no role or an unrecognised role
- **THEN** the session resolves to no authenticated user

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
