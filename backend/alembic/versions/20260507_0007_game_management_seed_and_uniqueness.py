"""game management seed support and one game one schedule

Revision ID: 20260507_0007
Revises: 20260507_0006
Create Date: 2026-05-07 18:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260507_0007"
down_revision: str | None = "20260507_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, app_id
            FROM task_schedules
            WHERE task_type = 'steam_review_sync' AND app_id IS NOT NULL
            ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
            """
        )
    ).fetchall()

    seen_app_ids: set[int] = set()
    delete_ids: list[int] = []
    for row in rows:
        row_id = int(row.id)
        app_id = int(row.app_id)
        if app_id in seen_app_ids:
            delete_ids.append(row_id)
            continue
        seen_app_ids.add(app_id)

    if delete_ids:
        bind.execute(sa.text("DELETE FROM task_schedules WHERE id IN :ids").bindparams(sa.bindparam("ids", expanding=True)), {"ids": delete_ids})

    op.create_unique_constraint(
        "uq_task_schedules_task_type_app_id",
        "task_schedules",
        ["task_type", "app_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_task_schedules_task_type_app_id", "task_schedules", type_="unique")
