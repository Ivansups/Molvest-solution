"""Черновик оператора на диалоге.

Revision ID: 002_operator_assist
Revises: 001_kb_core
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002_operator_assist"
down_revision: str | None = "001_kb_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("suggested_response", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "suggested_response")
