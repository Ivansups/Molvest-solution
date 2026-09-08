"""Маппинг тредов каналов и идемпотентность событий вебхуков.

Revision ID: 003_channel_threads
Revises: 002_operator_assist
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003_channel_threads"
down_revision: str | None = "002_operator_assist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("thread_id", sa.String(512), nullable=False),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "channel",
            "thread_id",
            "installation_id",
            name="uq_channel_threads_channel_thread_installation",
        ),
    )
    op.create_index(
        "ix_channel_threads_conversation_id",
        "channel_threads",
        ["conversation_id"],
    )
    op.add_column("messages", sa.Column("channel", sa.String(32), nullable=True))
    op.add_column(
        "messages", sa.Column("channel_message_id", sa.String(512), nullable=True)
    )
    op.create_index(
        "uq_messages_channel_message_id",
        "messages",
        ["channel", "channel_message_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_messages_channel_message_id", table_name="messages")
    op.drop_column("messages", "channel_message_id")
    op.drop_column("messages", "channel")
    op.drop_index("ix_channel_threads_conversation_id", table_name="channel_threads")
    op.drop_table("channel_threads")
