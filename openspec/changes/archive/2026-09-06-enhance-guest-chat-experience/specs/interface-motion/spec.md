## ADDED Requirements

### Requirement: Interface surfaces enter consistently
The frontend SHALL animate primary interface surfaces, including cards, headers,
navigation, tables, dialogs and message bubbles when they enter the UI. The
motion SHALL be brief and non-blocking.

#### Scenario: User opens an application screen
- **WHEN** a user loads a guest or support screen
- **THEN** its primary visual surfaces enter with the shared motion pattern

### Requirement: Motion respects user accessibility preferences
The frontend SHALL disable its custom motion animations when the user has
enabled `prefers-reduced-motion`.

#### Scenario: Reduced motion is enabled
- **WHEN** the browser reports `prefers-reduced-motion: reduce`
- **THEN** interface surfaces render without the custom entrance or pulse animations

### Requirement: New conversation control provides feedback
The guest chat's New conversation control SHALL have a distinct motion response
on entry and keyboard or pointer focus without changing the reset operation.

#### Scenario: Guest focuses the new conversation control
- **WHEN** the guest hovers over or focuses the control
- **THEN** its icon animates to confirm the control is interactive
