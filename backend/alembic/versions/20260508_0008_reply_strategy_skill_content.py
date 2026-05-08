"""add reply strategy skill content

Revision ID: 20260508_0008
Revises: 20260507_0007
Create Date: 2026-05-08 16:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260508_0008"
down_revision: str | Sequence[str] | None = "20260507_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reply_strategies",
        sa.Column("skill_content", sa.Text(), nullable=False, server_default=""),
    )
    op.execute(
        """
        UPDATE reply_strategies
        SET skill_content = COALESCE(NULLIF(prompt_template, ''), '')
        """
    )
    op.alter_column("reply_strategies", "skill_content", server_default=None)


def downgrade() -> None:
    op.drop_column("reply_strategies", "skill_content")
