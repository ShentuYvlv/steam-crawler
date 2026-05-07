"""multi game task schedules and sync job metadata

Revision ID: 20260507_0006
Revises: 20260506_0005
Create Date: 2026-05-07 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260507_0006"
down_revision: str | None = "20260506_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    op.add_column("task_schedules", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column("sync_jobs", sa.Column("schedule_id", sa.Integer(), nullable=True))
    op.add_column("sync_jobs", sa.Column("schedule_name", sa.String(length=255), nullable=True))
    op.add_column(
        "sync_jobs",
        sa.Column("trigger_type", sa.String(length=30), nullable=False, server_default="manual"),
    )
    op.create_index(op.f("ix_sync_jobs_schedule_id"), "sync_jobs", ["schedule_id"])
    op.create_foreign_key(
        "fk_sync_jobs_schedule_id_task_schedules",
        "sync_jobs",
        "task_schedules",
        ["schedule_id"],
        ["id"],
        ondelete="SET NULL",
    )

    for constraint in inspector.get_unique_constraints("task_schedules"):
        columns = constraint.get("column_names") or []
        if columns == ["task_type"]:
            op.drop_constraint(constraint["name"], "task_schedules", type_="unique")
            break

    op.execute(
        sa.text(
            """
            UPDATE task_schedules
            SET
                name = COALESCE(name, 'App ' || COALESCE(CAST(app_id AS VARCHAR), 'unknown') || ' 每日同步'),
                interval = 'daily',
                hour = COALESCE(hour, 0),
                minute = 0
            WHERE task_type = 'steam_review_sync'
            """
        )
    )
    op.alter_column("task_schedules", "name", nullable=False)

    op.execute(
        sa.text(
            """
            UPDATE sync_jobs
            SET trigger_type = COALESCE(trigger_type, 'manual')
            WHERE trigger_type IS NULL OR trigger_type = ''
            """
        )
    )
    op.alter_column("sync_jobs", "trigger_type", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "fk_sync_jobs_schedule_id_task_schedules",
        "sync_jobs",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_sync_jobs_schedule_id"), table_name="sync_jobs")
    op.drop_column("sync_jobs", "trigger_type")
    op.drop_column("sync_jobs", "schedule_name")
    op.drop_column("sync_jobs", "schedule_id")

    op.create_unique_constraint(None, "task_schedules", ["task_type"])
    op.drop_column("task_schedules", "name")
