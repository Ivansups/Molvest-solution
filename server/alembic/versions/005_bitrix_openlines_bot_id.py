"""id бота открытой линии у OAuth-записи портала.

Revision ID: 005_bitrix_openlines_bot_id
Revises: 004_bitrix_oauth_tokens
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005_bitrix_openlines_bot_id"
down_revision: str | None = "004_bitrix_oauth_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bitrix_oauth_tokens",
        sa.Column("openlines_bot_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bitrix_oauth_tokens", "openlines_bot_id")
