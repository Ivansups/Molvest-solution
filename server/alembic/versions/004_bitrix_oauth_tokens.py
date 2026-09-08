"""OAuth-токены локального приложения Bitrix24 (imconnector/imbot).

Revision ID: 004_bitrix_oauth_tokens
Revises: 003_channel_threads
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004_bitrix_oauth_tokens"
down_revision: str | None = "003_channel_threads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bitrix_oauth_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("member_id", sa.String(64), nullable=False, unique=True),
        sa.Column("access_token", sa.String(255), nullable=False),
        sa.Column("refresh_token", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("bitrix_oauth_tokens")
