## Purpose

Сценарий 3 ТЗ в Bitrix: скриншот 1С из онлайн-чата или коннектора доходит
до того же vision → RAG → порог, что и виджет.

## ADDED Requirements

### Requirement: Вложение Bitrix становится картинкой графа

When an accepted Bitrix bot or connector event carries an image, the
system SHALL obtain bytes and pass them as `image_base64` into
`run_chat_turn`. A direct URL whose host matches the portal MAY be
downloaded as today. If there is no safe URL but a file id is present,
the system SHALL download via Bitrix REST (`disk` / file get) using the
stored OAuth token. The guest message MAY have empty text when an image
is present.

#### Scenario: Прямой URL скачивается

- **WHEN** a guest Bitrix event includes an image URL on the portal host
- **THEN** the turn is processed with `image_base64` set and vision can run

#### Scenario: File id скачивается через REST

- **WHEN** a guest Bitrix event includes a file id and no safe URL
- **THEN** the system downloads the file via OAuth REST and processes the turn with `image_base64` set

#### Scenario: Картинка без текста не пустой ход

- **WHEN** a guest sends only a PNG/JPEG screenshot in the Bitrix online chat
- **THEN** the agent graph runs (vision then retrieve) and does not treat the turn as empty

### Requirement: Недоступное вложение не роняет вебхук

If the image cannot be downloaded, the system SHALL log a warning without
secrets, process any accompanying text (or a short placeholder if text is
absent), and return a normal processed status without HTTP 5xx.

#### Scenario: Сбой скачивания — текстовый ход

- **WHEN** file REST or URL download fails for a Bitrix attachment
- **THEN** the webhook still returns processed/ignored as appropriate, no guest reply is required from the failed image, and the process does not crash
