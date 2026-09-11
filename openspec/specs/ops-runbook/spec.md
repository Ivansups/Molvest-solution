## Purpose

Operations guide for the running system: environment variable names, health
check, knowledge-base management, runtime settings, and pointers to channel
runbooks. Startup instructions stay in README.

## Requirements

### Requirement: Operations guide exists beside startup README

The repository SHALL include `docs/OPS.md` describing how to operate the
running system after it is already started. The file SHALL cover: names of
environment variables (not secret values), `GET /health`, knowledge-base
upload/list/delete/reindex/PATCH, runtime settings (confidence threshold and
the three assist modes), and pointers to channel runbooks
(`docs/BITRIX.md`, `docs/REDMINE.md`). `README.md` SHALL remain the
startup/quick-start document and SHALL link to `docs/OPS.md`. The operations
guide SHALL NOT duplicate Make/troubleshooting from `docs/DEV.md` and SHALL
NOT document Grafana, SSE, or cloud deploy.

#### Scenario: Operator finds health and settings in OPS

- **WHEN** a reader opens `docs/OPS.md`
- **THEN** the file explains how to check `GET /health`, where to change the
  confidence threshold and assist mode, and how to manage knowledge-base
  documents including PATCH of title and metadata

#### Scenario: README points to operations, not the reverse dump

- **WHEN** a reader opens the root README
- **THEN** startup instructions stay there and a link to `docs/OPS.md` is
  present
