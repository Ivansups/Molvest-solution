"""Правила эскалации в runtime-настройках агента.

Revision ID: 008_escalation_rules
Revises: 007_agent_settings
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008_escalation_rules"
down_revision: str | None = "007_agent_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    "escalate_on_detector_failure",
    "escalate_on_low_rag",
    "skip_low_rag_on_image",
    "escalate_on_guest_handoff",
)


def upgrade() -> None:
    for name in _COLUMNS:
        op.add_column(
            "agent_settings",
            sa.Column(
                name,
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )


def downgrade() -> None:
    for name in reversed(_COLUMNS):
        op.drop_column("agent_settings", name)
