"""compatibility alias for task logs migration

Revision ID: 20260506_0005
Revises: 20260430_0005
Create Date: 2026-05-07 23:30:00.000000
"""

from collections.abc import Sequence

revision: str = "20260506_0005"
down_revision: str | None = "20260430_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    return None


def downgrade() -> None:
    return None
