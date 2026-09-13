"""Метка обработки диалога case learning.

Revision ID: 009_case_learning
Revises: 008_escalation_rules
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009_case_learning"
down_revision: str | None = "008_escalation_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("case_ingested_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "case_ingested_at")
