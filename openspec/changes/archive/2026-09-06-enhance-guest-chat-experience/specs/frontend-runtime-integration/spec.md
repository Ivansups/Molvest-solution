## ADDED Requirements

### Requirement: Local Docker development hydrates through loopback
The Next.js development server SHALL allow `127.0.0.1` to request its client
resources when the frontend runs in Docker locally.

#### Scenario: Guest opens local frontend through loopback
- **WHEN** a browser opens the Docker frontend at `http://127.0.0.1:3000`
- **THEN** Next.js loads client resources without blocking cross-origin dev requests and interactive controls work
