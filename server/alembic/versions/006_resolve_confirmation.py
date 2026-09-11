"""Подтверждение закрытия диалога оператором.

Revision ID: 006_resolve_confirmation
Revises: 005_bitrix_openlines_bot_id
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006_resolve_confirmation"
down_revision: str | None = "005_bitrix_openlines_bot_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("resolve_comment", sa.Text(), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("resolve_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "resolve_confirmed_at")
    op.drop_column("conversations", "resolve_comment")
