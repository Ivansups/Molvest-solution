"""Персистентность runtime-настроек агента (порог, режим).

Revision ID: 007_agent_settings
Revises: 006_resolve_confirmation
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007_agent_settings"
down_revision: str | None = "006_resolve_confirmation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("confidence_threshold", sa.Float(), nullable=False),
        sa.Column("operator_assist_mode", sa.String(length=16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("agent_settings")
