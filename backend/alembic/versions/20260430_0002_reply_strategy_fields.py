"""reply strategy configuration fields

Revision ID: 20260430_0002
Revises: 20260429_0001
Create Date: 2026-04-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260430_0002"
down_revision: str | None = "20260429_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reply_strategies", sa.Column("reply_rules", sa.Text(), nullable=True))
    op.add_column("reply_strategies", sa.Column("forbidden_terms", sa.JSON(), nullable=True))
    op.add_column("reply_strategies", sa.Column("good_examples", sa.JSON(), nullable=True))
    op.add_column("reply_strategies", sa.Column("brand_voice", sa.Text(), nullable=True))
    op.add_column(
        "reply_strategies",
        sa.Column("classification_strategy", sa.Text(), nullable=True),
    )
    op.add_column(
        "reply_strategies",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("reply_drafts", sa.Column("strategy_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("reply_drafts", "strategy_version")
    op.drop_column("reply_strategies", "version")
    op.drop_column("reply_strategies", "classification_strategy")
    op.drop_column("reply_strategies", "brand_voice")
    op.drop_column("reply_strategies", "good_examples")
    op.drop_column("reply_strategies", "forbidden_terms")
    op.drop_column("reply_strategies", "reply_rules")
