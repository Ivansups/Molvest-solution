## ADDED Requirements

### Requirement: Guest chat visibly reports response processing
The guest chat SHALL show an in-transcript processing indicator while its chat
mutation is pending. The indicator SHALL distinguish an image analysis from a
text response generation and SHALL disappear after either success or failure.

#### Scenario: Text response is being generated
- **WHEN** a guest submits a text question and `POST /chat` is pending
- **THEN** the transcript shows that the agent is forming a response

#### Scenario: Screenshot is being analysed
- **WHEN** a guest submits a message with an attached image and `POST /chat` is pending
- **THEN** the transcript shows that the image is being analysed

### Requirement: Guest chat exposes source excerpts
The guest chat SHALL render each returned source as an interactive document
control and SHALL reveal its `chunk_text` when the guest activates that control.

#### Scenario: Guest opens a source citation
- **WHEN** an assistant message has a source and the guest activates its document title
- **THEN** the UI shows the readable source fragment for that source

### Requirement: Guest can start a new local conversation
The guest chat SHALL provide a visible "New conversation" control that removes
`guest_conversation_id` from `sessionStorage` and clears the local transcript.
The next guest message SHALL be sent without a `conversation_id`.

#### Scenario: Guest resets a current conversation
- **WHEN** the guest activates "New conversation"
- **THEN** the transcript is empty and no guest conversation identifier remains in session storage

#### Scenario: Previous request finishes after reset
- **WHEN** the guest resets a conversation while its request is still pending
- **THEN** the late response does not restore the previous identifier or messages

#### Scenario: Guest sends after reset
- **WHEN** the guest submits the first message after a reset
- **THEN** the chat request has `conversation_id` set to null and backend creates a new conversation
