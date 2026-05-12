"""add game scope split

Revision ID: 20260512_0009
Revises: 20260508_0008
Create Date: 2026-05-12 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260512_0009"
down_revision: str | Sequence[str] | None = "20260508_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "steam_games",
        sa.Column("game_scope", sa.String(length=32), nullable=False, server_default="competitor"),
    )
    op.execute(
        """
        UPDATE steam_games
        SET game_scope = CASE
            WHEN app_id = 3350200 THEN 'owned'
            ELSE 'competitor'
        END
        """
    )
    op.alter_column("steam_games", "game_scope", server_default=None)


def downgrade() -> None:
    op.drop_column("steam_games", "game_scope")
